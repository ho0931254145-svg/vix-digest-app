"""Merge new daily closes into the page's chart and lookup data.

Usage: python -I update_data.py <page.html> <rows.json> <out.html>

rows.json maps trading dates to closes, e.g.
  {"2026-10-29": {"spx": 7750.1, "ndx": 26600.2, "dji": 52500.3, "vix": 16.5, "vix3m": 19.0}}
Any field may be null if that close is not available.

Updates three objects in the page script:
  DATA  one-year window for the VIX and index charts (keeps dates within one year of the latest)
  QD    full history since 2020 for the date lookup
  OV    current-year series for the yearly overlay chart (indices as % of prior year-end close)
The output has no publish skeleton, ready to publish as the artifact.
"""
import io, json, re, sys
from datetime import date

page, rows_path, out = sys.argv[1:4]
text = io.open(page, encoding='utf-8').read()
rows = json.load(io.open(rows_path, encoding='utf-8'))

# Strip the publish skeleton (one or more copies) if the page came from an artifact read
lines = text.split('\n')
while lines and lines[0].lower().startswith('<!doctype'):
    lines = lines[1:]
text = '\n'.join(lines).rstrip()
while text.endswith('</body></html>'):
    text = text[:-len('</body></html>')].rstrip()
text += '\n'


def grab(name):
    m = re.search(r'^const ' + name + r'=(\{.*?\});\s*$', text, re.M)
    if not m:
        sys.exit('missing const ' + name)
    return m, json.loads(m.group(1))


def put(name, obj):
    global text
    m, _ = grab(name)
    s = 'const %s=%s;' % (name, json.dumps(obj, ensure_ascii=False, separators=(',', ':')))
    text = text[:m.start()] + s + text[m.end():]


new_dates = sorted(rows)
added = []

# QD: full history
_, qd = grab('QD')
qmap = {'s': 'spx', 'n': 'ndx', 'j': 'dji', 'v': 'vix', 'v3': 'vix3m'}
for d in new_dates:
    r = rows[d]
    if d in qd['d']:
        i = qd['d'].index(d)
        for qk, rk in qmap.items():
            if r.get(rk) is not None:
                qd[qk][i] = r[rk]
        continue
    if d < qd['d'][-1]:
        sys.exit('date %s is older than the latest page date %s and not in the page' % (d, qd['d'][-1]))
    qd['d'].append(d)
    for qk, rk in qmap.items():
        qd[qk].append(r.get(rk))
    added.append(d)
put('QD', qd)

# DATA: one-year window (charts need every series filled)
_, data = grab('DATA')
for d in new_dates:
    r = rows[d]
    vals = {k: r.get(k) for k in ('spx', 'vix', 'vix3m', 'ndx', 'dji')}
    if any(v is None for v in vals.values()):
        print('DATA: skipped %s, a close is missing: %s' % (d, vals))
        continue
    if d in data['d']:
        i = data['d'].index(d)
        for k, v in vals.items():
            data[k][i] = v
    else:
        data['d'].append(d)
        for k, v in vals.items():
            data[k].append(v)
last = date.fromisoformat(data['d'][-1])
try:
    cut = last.replace(year=last.year - 1).isoformat()
except ValueError:  # Feb 29
    cut = last.replace(year=last.year - 1, day=28).isoformat()
keep = [i for i, d in enumerate(data['d']) if d >= cut]
for k in data:
    data[k] = [data[k][i] for i in keep]
put('DATA', data)

# OV: current-year overlay
_, ov = grab('OV')
for d in new_dates:
    yr = d[:4]
    if yr not in ov['dates']:
        print('OV: year %s has no series in the page; the overlay chart script (YEARS, COL) must be extended by hand' % yr)
        continue
    if d in ov['dates'][yr]:
        continue
    prev = [i for i, x in enumerate(qd['d']) if x[:4] == str(int(yr) - 1)]
    base_i = prev[-1]
    r = rows[d]
    ov['dates'][yr].append(d)
    for k, qk in (('spx', 's'), ('ndx', 'n'), ('dji', 'j')):
        base = qd[qk][base_i]
        v = r.get(k)
        ov[k][yr].append(round(v / base * 100, 2) if v is not None and base else ov[k][yr][-1])
    v = r.get('vix')
    ov['vix'][yr].append(v if v is not None else ov['vix'][yr][-1])
put('OV', ov)

io.open(out, 'w', encoding='utf-8', newline='\n').write(text)
print('added dates:', ', '.join(added) or 'none')
print('DATA window: %s to %s (%d days)' % (data['d'][0], data['d'][-1], len(data['d'])))
