"""Add the digest's latest trading day to the history log the App reads.

Usage: python -I history.py <page.html> [data/history.json]

Writes one row per US trading day: VIX, VIX3M, the VIX3M − VIX spread, the
long score (0–10) and suggested position (%) as the page states them, the VIX
state label, and the S&P 500 / NASDAQ / Dow / Russell 2000 closes.
Running it twice for the same day replaces that day's row, so it is safe to rerun.
When the day before is missing from the log, it is added too, from the page's
own "previous → today" figures (marked src "前日回推").

Exit codes: 0 written, 1 page could not be read (log left unchanged).
"""
import io, json, os, sys
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pagedata

sys.stdout.reconfigure(encoding='utf-8')
page = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'history.json')

text = pagedata.load(page)
today, prev = pagedata.day(text, -1), pagedata.day(text, -2)
v = pagedata.verdict(text)
hd, ab = v.get('header') or {}, v.get('appbar') or {}
score, pos = ab.get('score', hd.get('score')), ab.get('pos', hd.get('pos'))
if not today or score is None or pos is None:
    sys.exit('could not read the date, score or position from %s; history left unchanged' % page)

log = {'rows': []}
if os.path.exists(out):
    log = json.load(io.open(out, encoding='utf-8'))
rows = {r['d']: r for r in log.get('rows', [])}


def as_int(x):
    return int(x) if x is not None and float(x).is_integer() else x


rows[today['d']] = dict(today, score=as_int(score), pos=as_int(pos), state=v.get('state'),
                        term=hd.get('term'), src='日報')
if prev and prev['d'] not in rows and hd.get('score_prev') is not None and hd.get('pos_prev') is not None:
    rows[prev['d']] = dict(prev, score=as_int(hd['score_prev']), pos=as_int(hd['pos_prev']), state=None,
                           term=None, src='前日回推')

log = {
    'note': '每日強勢族群與 VIX 日報的歷史紀錄；每個美股交易日一列，由 tools/history.py 從日報網頁抽出。',
    'updated': datetime.now(ZoneInfo('Asia/Taipei')).isoformat(timespec='seconds'),
    'fields': {'d': '美股交易日', 'vix': 'VIX 收盤', 'vix3m': 'VIX3M 收盤', 'spread': 'VIX3M − VIX',
               'score': '做多評分（/10）', 'pos': '建議倉位（%）', 'state': 'VIX 狀態', 'term': '期限結構（日報原文）',
               'spx': 'S&P 500', 'ndx': 'NASDAQ', 'dji': '道瓊', 'rut': 'Russell 2000', 'src': '來源'},
    'rows': [rows[d] for d in sorted(rows)],
}
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
tmp = out + '.new'
io.open(tmp, 'w', encoding='utf-8', newline='\n').write(json.dumps(log, ensure_ascii=False, indent=1) + '\n')
os.replace(tmp, out)
r = rows[today['d']]
print('history: %s  VIX %s  spread %+.2f  score %s/10  position %s%%  (%d rows)'
      % (r['d'], r['vix'], r['spread'] or 0, r['score'], r['pos'], len(log['rows'])))
