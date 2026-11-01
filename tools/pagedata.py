"""Read the figures the history log and the watchdog need out of a digest page.

Used by history.py and watchdog.py; not run on its own.
The page is the publish-ready digest (src/page.html, or an artifact read of it).
Every field is optional: a missing one comes back as None so callers can report it.
"""
import io, json, re

NUM = r'([0-9][0-9,]*(?:\.[0-9]+)?)'


def load(path):
    return io.open(path, encoding='utf-8').read()


def const(text, name):
    m = re.search(r'^const ' + name + r'=(\{.*?\});\s*$', text, re.M)
    return json.loads(m.group(1)) if m else None


def _num(s):
    return None if s is None else float(s.replace(',', ''))


def _pair(text):
    """'5 → 4 / 10' -> (5, 4); '4 / 10' -> (None, 4); '50% → 40%' -> (50, 40)."""
    if text is None:
        return None, None
    nums = re.findall(r'[0-9]+(?:\.[0-9]+)?', text.split('/')[0])
    if '→' in text and len(nums) >= 2:
        return float(nums[0]), float(nums[1])
    return (None, float(nums[0])) if nums else (None, None)


def day(text, i=-1):
    """Figures for one trading day of the page: i=-1 latest, i=-2 the day before."""
    qd, px = const(text, 'QD'), const(text, 'PX')
    if not qd:
        return None
    row = {'d': qd['d'][i]}
    for k, name in (('s', 'spx'), ('n', 'ndx'), ('j', 'dji'), ('v', 'vix'), ('v3', 'vix3m')):
        row[name] = qd.get(k, [None] * len(qd['d']))[i]
    rut = None
    if px and '^RUT' in px.get('t', {}) and row['d'] in px['d']:
        rut = px['t']['^RUT']['c'][px['d'].index(row['d'])]
    row['rut'] = rut
    row['spread'] = round(row['vix3m'] - row['vix'], 2) if row['vix'] is not None and row['vix3m'] is not None else None
    return row


def verdict(text):
    """The judgement as the page states it, in each place it states it."""
    out = {}
    ab = re.search(r'<div class="ab-s">\s*<span>VIX <b>' + NUM + r'</b></span>\s*<span>評分 <b>' + NUM +
                   r'</b>/10</span>\s*<span>倉位 <b>' + NUM + r'%</b></span>', text)
    out['appbar'] = {'vix': _num(ab.group(1)), 'score': _num(ab.group(2)), 'pos': _num(ab.group(3))} if ab else None
    vd = re.search(r'<div class="verdict"><span>期限結構<b>([^<]*)</b></span><span>做多評分<b>([^<]*)</b></span>'
                   r'<span>建議倉位<b>([^<]*)</b></span></div>', text)
    if vd:
        sp, sc = _pair(vd.group(2))
        pp, pc = _pair(vd.group(3))
        out['header'] = {'term': vd.group(1).strip(), 'score_prev': sp, 'score': sc, 'pos_prev': pp, 'pos': pc}
    else:
        out['header'] = None
    vs = re.search(r'<div class="vsum">(.*?)</div>\s*</div>', text, re.S)
    if vs:
        cells = dict(re.findall(r'<span class="k">([^<]*)</span><b>([^<]*)</b>', vs.group(1)))
        sp, sc = _pair(cells.get('做多環境評分'))
        pp, pc = _pair(cells.get('建議倉位'))
        out['vsum'] = {'state': cells.get('狀態'), 'term': cells.get('期限結構'), 'score_prev': sp, 'score': sc,
                       'pos_prev': pp, 'pos': pc}
    else:
        out['vsum'] = None
    st = re.search(r'<div class="vixcell">.*?<span class="ch[^"]*">([^<]*)</span>', text, re.S)
    out['state'] = st.group(1).split('・')[-1].strip() if st and '・' in st.group(1) else (out['vsum'] or {}).get('state')
    lv = re.search(r'<span class="live">([^<]*)</span>', text)
    out['live'] = lv.group(1).strip() if lv else None
    return out
