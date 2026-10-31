"""Sanity checks on src/page.html before building and pushing.

Usage: python -I check_page.py <page.html>

Fails (exit 1) when the data objects do not parse, their latest dates disagree,
the Google Fonts <link> line is missing or doubled, the headline still shows an
older date than the data, or the scripts look truncated.
"""
import io, json, re, sys

sys.stdout.reconfigure(encoding='utf-8')
t = io.open(sys.argv[1], encoding='utf-8').read()
errors = []


def grab(name):
    m = re.search(r'^const ' + name + r'=(\{.*?\});\s*$', t, re.M)
    if not m:
        errors.append('missing const ' + name)
        return None
    try:
        return json.loads(m.group(1))
    except ValueError as e:
        errors.append('const %s does not parse: %s' % (name, e))


px, qd, data, ov = grab('PX'), grab('QD'), grab('DATA'), grab('OV')
if px and qd and data:
    lasts = {'PX': px['d'][-1], 'QD': qd['d'][-1], 'DATA': data['d'][-1]}
    if len(set(lasts.values())) != 1:
        errors.append('latest dates disagree: %s' % lasts)
    latest = qd['d'][-1]
    y, m, d = latest.split('-')
    md = '%d/%d' % (int(m), int(d))
    for label, pat in (('app bar', r'<div class="ab-t">.*?<span>([^<]*)</span>'),
                       ('eyebrow', r'<span class="live">([^<]*)</span>')):
        hit = re.search(pat, t)
        if not hit:
            errors.append('%s not found' % label)
        elif md not in hit.group(1) and latest not in hit.group(1):
            errors.append('%s shows "%s", expected the latest date %s' % (label, hit.group(1), latest))
    for name, o in (('PX', px), ('QD', qd), ('DATA', data)):
        series = o['t'].values() if name == 'PX' else [v for k, v in o.items() if k != 'd']
        n = len(o['d'])
        for s in series:
            arr = s['c'] if name == 'PX' else s
            if len(arr) != n:
                errors.append('%s has a series of length %d, dates %d' % (name, len(arr), n))
                break
    print('latest trading date: %s (%s)' % (latest, md))

links = [l for l in t.split('\n') if l.startswith('<link rel="stylesheet" href="https://fonts.googleapis.com')]
if len(links) != 1:
    errors.append('expected exactly one Google Fonts <link> line, found %d' % len(links))
if t.lower().startswith('<!doctype'):
    errors.append('page starts with a document skeleton; it must be the publish-ready page')
opens, closes = len(re.findall(r'<script\b', t)), len(re.findall(r'</script>', t))
if opens != closes:
    errors.append('<script> tags unbalanced: %d open, %d close' % (opens, closes))
if 'serviceWorker' not in t or 'manifest.webmanifest' not in t:
    errors.append('PWA hooks (manifest link or service worker registration) are missing')

if errors:
    print('FAILED:\n  ' + '\n  '.join(errors))
    sys.exit(1)
print('page checks passed')
