"""Append the latest US closes to the page's data, in place.

Usage: python -I daily_data.py <page.html> [--asof YYYY-MM-DD]

1. Fetches daily bars from Yahoo Finance for every ticker in PX (the one-year
   price table behind the trend chart and watchlist).
2. Appends each completed trading day after the page's latest PX date, updates
   volume (v) and 3-month average volume (av), and keeps a one-year window.
3. Writes rows.json next to the page and runs update_data.py on it, which
   updates DATA, QD and OV (S&P 500, NASDAQ Composite, Dow, VIX, VIX3M).
4. Prints a summary (index closes, ETF and stock day moves) to write the text from.

A trading day counts as completed once it is before today in New York, or it is
today and past 16:30 New York time. --asof stops at that date instead.
Exits with code 3 when there is no new trading day, leaving the page untouched.
"""
import io, json, os, re, subprocess, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.stdout.reconfigure(encoding='utf-8')
args = sys.argv[1:]
page = args[0]
asof = args[args.index('--asof') + 1] if '--asof' in args else None
here = os.path.dirname(os.path.abspath(__file__))
NY = ZoneInfo('America/New_York')
INDEX_ROWS = {'spx': '^GSPC', 'ndx': '^IXIC', 'dji': '^DJI', 'vix': '^VIX', 'vix3m': '^VIX3M'}

text = io.open(page, encoding='utf-8').read()
m = re.search(r'^const PX=(\{.*?\});\s*$', text, re.M)
if not m:
    sys.exit('missing const PX')
px = json.loads(m.group(1))
last_page = px['d'][-1]

now_ny = datetime.now(NY)
cutoff = now_ny.date() if now_ny.hour * 60 + now_ny.minute >= 16 * 60 + 30 else now_ny.date() - timedelta(days=1)
if asof:
    cutoff = min(cutoff, date.fromisoformat(asof))


def fetch(sym):
    url = 'https://query1.finance.yahoo.com/v8/finance/chart/%s?range=3mo&interval=1d' % urllib.parse.quote(sym)
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            r = json.load(urllib.request.urlopen(req, timeout=20))['chart']['result'][0]
            q = r['indicators']['quote'][0]
            bars = {}
            for ts, c, v in zip(r.get('timestamp') or [], q.get('close') or [], q.get('volume') or []):
                d = datetime.fromtimestamp(ts, NY).date().isoformat()
                bars[d] = (round(c, 3 if c < 10 else 2) if c is not None else None, v)
            return sym, bars
        except Exception as e:
            err = e
            time.sleep(1.5 * (attempt + 1))
    print('fetch failed: %s (%s)' % (sym, err))
    return sym, None


with ThreadPoolExecutor(8) as ex:
    bars = dict(ex.map(fetch, list(px['t'])))

# New trading days: dates after the page's latest that the S&P 500 has a close for
ref = bars.get('^GSPC') or {}
new_dates = sorted(d for d, (c, _) in ref.items() if d > last_page and d <= cutoff.isoformat() and c is not None)
if not new_dates:
    print('no new trading day after %s (cutoff %s); page unchanged' % (last_page, cutoff))
    sys.exit(3)

missing = [s for s, b in bars.items() if b is None]
for d in new_dates:
    px['d'].append(d)
    for sym, t in px['t'].items():
        b = (bars.get(sym) or {}).get(d)
        t['c'].append(b[0] if b else None)
for sym, t in px['t'].items():
    b = bars.get(sym)
    if not b or 'v' not in t:
        continue
    vols = [v for d, (c, v) in sorted(b.items()) if d <= new_dates[-1] and v]
    if vols:
        last_v = b.get(new_dates[-1], (None, None))[1]
        if last_v:
            t['v'] = last_v
        t['av'] = round(sum(vols[-63:]) / len(vols[-63:]))

last = date.fromisoformat(px['d'][-1])
try:
    cut = last.replace(year=last.year - 1).isoformat()
except ValueError:  # Feb 29
    cut = last.replace(year=last.year - 1, day=28).isoformat()
keep = [i for i, d in enumerate(px['d']) if d > cut]
px['d'] = [px['d'][i] for i in keep]
for t in px['t'].values():
    t['c'] = [t['c'][i] for i in keep]

s = 'const PX=%s;' % json.dumps(px, ensure_ascii=False, separators=(',', ':'))
text = text[:m.start()] + s + text[m.end():]
io.open(page, 'w', encoding='utf-8', newline='\n').write(text)

rows = {}
for d in new_dates:
    rows[d] = {k: ((bars.get(sym) or {}).get(d) or (None,))[0] for k, sym in INDEX_ROWS.items()}
rows_path = os.path.join(os.path.dirname(os.path.abspath(page)), 'rows.json')
json.dump(rows, io.open(rows_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
subprocess.run([sys.executable, '-I', os.path.join(here, 'update_data.py'), page, rows_path, page], check=True)

# Summary for writing the day's text
print('\nnew dates:', ', '.join(new_dates), '| PX window %s to %s (%d days)' % (px['d'][0], px['d'][-1], len(px['d'])))
if missing:
    print('no data for:', ', '.join(missing))
print('rows.json:', json.dumps(rows, ensure_ascii=False))


def chg(t):
    c = [x for x in t['c'] if x is not None]
    return (c[-1], (c[-1] / c[-2] - 1) * 100) if len(c) >= 2 and t['c'][-1] is not None else (None, None)


print('\n== indices (%s) ==' % new_dates[-1])
for sym, t in px['t'].items():
    if sym[0] == '^':
        c, p = chg(t)
        print('%-7s %-22s %12s %+7.2f%%' % (sym, t['n'], '{:,.2f}'.format(c) if c else '—', p or 0))
for ty, label in (('ETF', 'ETF'), ('EQUITY', 'stocks')):
    moves = sorted(((chg(t)[1], sym, t) for sym, t in px['t'].items() if t.get('ty') == ty and chg(t)[1] is not None), key=lambda x: -x[0])
    print('\n== %s: top 15 / bottom 10 of %d ==' % (label, len(moves)))
    for p, sym, t in moves[:15] + [(None, '…', None)] + moves[-10:]:
        if t is None:
            print('  …')
            continue
        vx = (t['v'] / t['av']) if t.get('v') and t.get('av') else None
        print('  %-6s %+7.2f%%  vol x%s  %s' % (sym, p, '%.2f' % vx if vx else '—', t.get('ind', '')))
