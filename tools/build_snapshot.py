"""Build the desktop app's offline snapshot from the publish-ready page.

Usage: python -I build_snapshot.py <page.html> <out index.html>

Replaces the Google Fonts <link> with @font-face rules whose fonts are subset to
the characters on the page and embedded as data URIs, and wraps the page in a
full HTML document. Font files are read from the fonts/ folder next to this script.
The document head also loads app-extra.js, which adds the history and watchdog
panel from data/*.json; it lives only in the App, never in the digest page.
"""
import base64, io, os, sys
from fontTools import subset
from fontTools.ttLib import TTFont

page, out = sys.argv[1:3]
fontdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
text = io.open(page, encoding='utf-8').read()

chars = set(text) | {chr(c) for c in range(0x20, 0x7f)} | set('−–—…‘’“”・，。、：；！？（）「」《》％＋＝≈→←↑↓×÷°')
unicodes = sorted(ord(c) for c in chars if ord(c) >= 0x20)
faces = [('Noto Sans TC', 400, 'tc-400'), ('Noto Sans TC', 500, 'tc-500'), ('Noto Sans TC', 700, 'tc-700'), ('Noto Sans TC', 900, 'tc-900'),
         ('IBM Plex Mono', 400, 'mono-400'), ('IBM Plex Mono', 600, 'mono-600'),
         ('IBM Plex Sans Condensed', 500, 'cond-500'), ('IBM Plex Sans Condensed', 600, 'cond-600')]
css = []
for fam, w, name in faces:
    opts = subset.Options()
    opts.flavor = 'woff'
    opts.layout_features = ['*']
    opts.name_IDs = ['*']
    opts.notdef_outline = True
    f = TTFont(os.path.join(fontdir, name + '.ttf'))
    s = subset.Subsetter(opts)
    s.populate(unicodes=unicodes)
    s.subset(f)
    buf = io.BytesIO()
    f.flavor = 'woff'
    f.save(buf)
    css.append("@font-face{font-family:'%s';font-style:normal;font-weight:%d;font-display:swap;src:url(data:font/woff;base64,%s) format('woff')}"
               % (fam, w, base64.b64encode(buf.getvalue()).decode()))
block = '<style>\n/* Fonts embedded for offline use: subset to the characters on this page */\n' + '\n'.join(css) + '\n</style>'

lines = text.rstrip('\n').split('\n')
idx = [i for i, l in enumerate(lines) if l.startswith('<link rel="stylesheet" href="https://fonts.googleapis.com')]
if len(idx) != 1:
    sys.exit('expected exactly one Google Fonts <link> line, found %d' % len(idx))
lines[idx[0]] = block
skeleton = ('<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            '<style>[hidden]{display:none!important}body{margin:0}</style>'
            '<script src="app-extra.js" defer></script></head><body>')
io.open(out, 'w', encoding='utf-8', newline='\n').write(skeleton + '\n' + '\n'.join(lines) + '\n</body></html>\n')
print('wrote %s (%d KB, %d characters subset)' % (out, os.path.getsize(out) // 1024, len(unicodes)))
