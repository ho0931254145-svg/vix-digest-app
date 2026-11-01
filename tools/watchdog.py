"""Watchdog: check that today's digest and App are complete and consistent, and record the result.

Usage: python -I watchdog.py [--artifact <digest page file>] [--repo <repo dir>] [--out data/status.json]

Run from the repo after `git fetch origin && git reset --hard origin/main`, with the
digest artifact read to a local file. It never changes the digest or the App page;
it only writes data/status.json, which the App shows as a badge.

Checks (each is ok / fail / skip):
  trade_day  latest completed US trading day (Yahoo ^GSPC daily bars)
  digest     the digest artifact covers that day
  app_src    src/page.html (the App's content) covers that day
  app_live   the published index.html shows that day (live site; falls back to origin/main)
  history    data/history.json has that day, with the page's score and position
  closes     S&P 500, NASDAQ, Dow, Russell 2000, VIX, VIX3M match Yahoo closes for that day
  verdict    score and position agree in the app bar, header and VIX summary,
             and "previous → today" matches the history log's previous day
  term       the term-structure label agrees with VIX3M − VIX

Exit codes: 0 all checks pass, 2 at least one check failed, 1 the watchdog itself broke.
"""
import argparse, io, json, os, re, subprocess, sys, urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pagedata

sys.stdout.reconfigure(encoding='utf-8')
NY, TPE = ZoneInfo('America/New_York'), ZoneInfo('Asia/Taipei')
LIVE = 'https://ho0931254145-svg.github.io/vix-digest-app/'
TOL = {'spx': 0.0015, 'ndx': 0.0015, 'dji': 0.0015, 'rut': 0.0015, 'vix': 0.015, 'vix3m': 0.015}
YSYM = {'spx': '^GSPC', 'ndx': '^IXIC', 'dji': '^DJI', 'rut': '^RUT', 'vix': '^VIX', 'vix3m': '^VIX3M'}
NAME = {'spx': 'S&P 500', 'ndx': 'NASDAQ', 'dji': '道瓊', 'rut': 'Russell 2000', 'vix': 'VIX', 'vix3m': 'VIX3M'}

ap = argparse.ArgumentParser()
ap.add_argument('--artifact')
ap.add_argument('--repo', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
ap.add_argument('--out')
a = ap.parse_args()
repo = os.path.abspath(a.repo)
out = a.out or os.path.join(repo, 'data', 'status.json')
checks = []


def add(cid, name, state, detail):
    checks.append({'id': cid, 'name': name, 'state': state, 'detail': detail})
    print('%-5s %-9s %s' % (state.upper(), cid, detail))


def yahoo(sym):
    url = 'https://query1.finance.yahoo.com/v8/finance/chart/%s?range=1mo&interval=1d' % urllib.request.quote(sym)
    r = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=20))
    r = r['chart']['result'][0]
    return {datetime.fromtimestamp(ts, NY).date().isoformat(): c
            for ts, c in zip(r['timestamp'], r['indicators']['quote'][0]['close']) if c is not None}


def md(d):
    y, m, dd = d.split('-')
    return '%d/%d' % (int(m), int(dd))


try:
    src_text = pagedata.load(os.path.join(repo, 'src', 'page.html'))
    app = pagedata.day(src_text)

    # 1. latest completed trading day
    latest, ycache = None, {}
    try:
        now = datetime.now(NY)
        cutoff = now.date() if now.hour * 60 + now.minute >= 16 * 60 + 30 else now.date() - timedelta(days=1)
        ycache['spx'] = yahoo(YSYM['spx'])
        latest = max(d for d in ycache['spx'] if d <= cutoff.isoformat())
        add('trade_day', '最新交易日', 'ok', '最近一個已收盤的美股交易日是 %s' % latest)
    except Exception as e:
        latest = app['d'] if app else None
        add('trade_day', '最新交易日', 'skip', '取不到 Yahoo 日線（%s），以下改用 App 的資料日期 %s' % (e, latest))

    # 2. digest artifact
    if a.artifact and os.path.exists(a.artifact):
        dg = pagedata.day(pagedata.load(a.artifact))
        if not dg:
            add('digest', '日報網頁', 'fail', '讀到的日報網頁沒有 QD 資料')
        elif dg['d'] < latest:
            add('digest', '日報網頁', 'fail', '日報網頁停在 %s，未更新到 %s' % (dg['d'], latest))
        else:
            add('digest', '日報網頁', 'ok', '日報網頁涵蓋 %s' % dg['d'])
    else:
        add('digest', '日報網頁', 'skip', '沒有提供日報網頁檔案')

    # 3. App source
    if not app:
        add('app_src', 'App 內容', 'fail', 'src/page.html 沒有 QD 資料')
    elif app['d'] < latest:
        add('app_src', 'App 內容', 'fail', 'App 內容停在 %s，未更新到 %s' % (app['d'], latest))
    else:
        add('app_src', 'App 內容', 'ok', 'App 內容涵蓋 %s' % app['d'])

    # 4. published page
    want = '<span>%s 收盤</span>' % md(latest)
    try:
        req = urllib.request.Request(LIVE + '?v=' + datetime.now().strftime('%H%M%S'), headers={'User-Agent': 'Mozilla/5.0'})
        live = urllib.request.urlopen(req, timeout=20).read().decode('utf-8', 'replace')
        add('app_live', '線上 App', 'ok' if want in live else 'fail',
            '線上 App 顯示 %s 收盤' % md(latest) if want in live else '線上 App 還沒顯示 %s 收盤' % md(latest))
    except Exception as e:
        try:
            main = subprocess.run(['git', '-C', repo, 'show', 'origin/main:index.html'], capture_output=True, text=True,
                                  encoding='utf-8', check=True).stdout
            ok = want in main
            add('app_live', '線上 App', 'ok' if ok else 'fail',
                '線上網址連不到（%s），改查 main 分支：index.html %s %s 收盤' % (type(e).__name__, '顯示' if ok else '未顯示', md(latest)))
        except Exception as e2:
            add('app_live', '線上 App', 'skip', '線上網址與 main 分支都讀不到（%s；%s）' % (e, e2))

    # 5. history log
    v = pagedata.verdict(src_text)
    ab, hd, vs = v.get('appbar') or {}, v.get('header') or {}, v.get('vsum') or {}
    hpath = os.path.join(repo, 'data', 'history.json')
    rows = json.load(io.open(hpath, encoding='utf-8'))['rows'] if os.path.exists(hpath) else []
    by = {r['d']: r for r in rows}
    hr = by.get(app['d']) if app else None
    if not hr:
        add('history', '歷史紀錄', 'fail', '歷史紀錄沒有 %s 這一列' % (app['d'] if app else '?'))
    elif hr.get('score') != ab.get('score') or hr.get('pos') != ab.get('pos'):
        add('history', '歷史紀錄', 'fail', '歷史紀錄 %s 為評分 %s、倉位 %s%%，頁面為 %s、%s%%'
            % (hr['d'], hr.get('score'), hr.get('pos'), '%g' % ab['score'] if ab.get('score') is not None else '?',
               '%g' % ab['pos'] if ab.get('pos') is not None else '?'))
    elif app['d'] < latest:
        add('history', '歷史紀錄', 'fail', '歷史紀錄最新到 %s，缺 %s' % (rows[-1]['d'] if rows else '?', latest))
    else:
        add('history', '歷史紀錄', 'ok', '歷史紀錄已有 %s（共 %d 列）' % (hr['d'], len(rows)))

    # 6. closes against Yahoo
    if app:
        bad, done, miss = [], [], []
        for k in ('spx', 'ndx', 'dji', 'rut', 'vix', 'vix3m'):
            try:
                ref = (ycache.get(k) or yahoo(YSYM[k])).get(app['d'])
            except Exception:
                ref = None
            mine = app.get(k)
            if ref is None or mine is None:
                miss.append(NAME[k])
                continue
            diff = mine / ref - 1
            (bad if abs(diff) > TOL[k] else done).append('%s %s（Yahoo %s，差 %+.2f%%）' % (NAME[k], mine, round(ref, 2), diff * 100))
        if bad:
            add('closes', '收盤核對', 'fail', '與 Yahoo 差距超過容許值：' + '；'.join(bad))
        elif done:
            add('closes', '收盤核對', 'ok', '%d 項一致%s' % (len(done), '；未取得：' + '、'.join(miss) if miss else ''))
        else:
            add('closes', '收盤核對', 'skip', '取不到 Yahoo 收盤：' + '、'.join(miss))

    # 7. verdict consistency
    probs = []
    places = [('頂端列', ab), ('頁首', hd), ('VIX 研判總覽', vs)]
    have = [(n, p) for n, p in places if p and p.get('score') is not None]
    if len(have) < 3:
        probs.append('找不到：' + '、'.join(n for n, p in places if not (p and p.get('score') is not None)))
    for key, label in (('score', '評分'), ('pos', '倉位')):
        vals = {n: p.get(key) for n, p in have}
        if len(set(vals.values())) > 1:
            probs.append('%s不一致：%s' % (label, '、'.join('%s %s' % (n, int(x) if x is not None else '?') for n, x in vals.items())))
    prev_rows = [r for r in rows if app and r['d'] < app['d']]
    if prev_rows and hd.get('score_prev') is not None:
        pr = prev_rows[-1]
        if pr.get('score') != hd.get('score_prev') or pr.get('pos') != hd.get('pos_prev'):
            probs.append('頁首的前日值 %s 分／%s%% 與歷史紀錄 %s 的 %s 分／%s%% 不同'
                         % (int(hd['score_prev']), int(hd['pos_prev']), pr['d'], pr.get('score'), pr.get('pos')))
    add('verdict', '評分與倉位', 'fail' if probs else 'ok',
        '；'.join(probs) if probs else '評分 %s/10、倉位 %s%%，三處一致' % (int(ab['score']), int(ab['pos'])))

    # 8. term structure label vs numbers
    term, spread = hd.get('term') or '', app.get('spread') if app else None
    if spread is None or not term:
        add('term', '期限結構', 'skip', '缺 VIX3M 或期限結構文字')
    else:
        probs = []
        if 'Contango' in term and spread <= 0:
            probs.append('標示 Contango，但 VIX3M − VIX = %+.2f' % spread)
        if ('逆價差' in term or 'Backwardation' in term) and spread >= 0:
            probs.append('標示逆價差，但 VIX3M − VIX = %+.2f' % spread)
        n = re.search(r'([+−-]\s*[0-9]+(?:\.[0-9]+)?)', term)
        if n:
            stated = float(n.group(1).replace('−', '-').replace(' ', ''))
            if abs(stated - spread) > 0.02:
                probs.append('標示 %+.2f，資料算出 %+.2f' % (stated, spread))
        add('term', '期限結構', 'fail' if probs else 'ok', '；'.join(probs) if probs else '%s 與 VIX3M − VIX = %+.2f 一致' % (term, spread))

    status = 0 if all(c['state'] != 'fail' for c in checks) else 2
except Exception as e:
    add('watchdog', 'Watchdog', 'fail', 'Watchdog 本身出錯：%s: %s' % (type(e).__name__, e))
    status, latest = 1, locals().get('latest')

fails = [c for c in checks if c['state'] == 'fail']
result = {
    'date': latest,
    'checked_at': datetime.now(TPE).isoformat(timespec='seconds'),
    'ok': not fails,
    'summary': '全部通過' if not fails else '%d 項異常：%s' % (len(fails), '、'.join(c['name'] for c in fails)),
    'checks': checks,
}
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
io.open(out, 'w', encoding='utf-8', newline='\n').write(json.dumps(result, ensure_ascii=False, indent=1) + '\n')
print('status: %s -> %s' % (result['summary'], out))
sys.exit(status)
