"""Turn a built index.html back into the publish-ready page (the reverse of build_snapshot.py).

Usage: python -I unsnapshot.py <index.html> <font link page.html> <out page.html>

Drops the document skeleton and replaces the embedded @font-face block with the
Google Fonts <link> line taken from the second argument (normally the current
src/page.html). deploy.sh uses this so src/page.html always matches what is live.
"""
import io, re, sys

snap, link_src, out = sys.argv[1:4]
text = io.open(snap, encoding='utf-8').read()
link = [l for l in io.open(link_src, encoding='utf-8').read().split('\n')
        if l.startswith('<link rel="stylesheet" href="https://fonts.googleapis.com')]
if len(link) != 1:
    sys.exit('expected exactly one Google Fonts <link> line in %s, found %d' % (link_src, len(link)))

lines = text.rstrip('\n').split('\n')
if not lines[0].lower().startswith('<!doctype'):
    sys.exit('%s does not start with the snapshot skeleton' % snap)
lines = lines[1:]
if lines[-1] != '</body></html>':
    sys.exit('%s does not end with </body></html>' % snap)
lines = lines[:-1]
body = '\n'.join(lines)
block = re.compile(r'^<style>\n/\* Fonts embedded for offline use[^\n]*\n(?:@font-face[^\n]*\n)+</style>$', re.M)
body, n = block.subn(lambda m: link[0], body)
if n != 1:
    sys.exit('expected exactly one embedded font block, found %d' % n)
io.open(out, 'w', encoding='utf-8', newline='\n').write(body + '\n')
print('wrote %s' % out)
