"""Copy the published digest page into src/page.html if it covers the latest US trading day.

Usage: python -I mirror.py <artifact page.html> [src/page.html]

The digest is written by the routine 每日強勢族群與 VIX 和四大指數研究, which republishes
https://claude.ai/artifact/BvJ5h6vb55n3F6DiYRqLWo every US trading day around 07:45 Taipei.
Read that artifact to a local file first, then pass the file here.

Exit codes:
  0  src/page.html updated to the artifact (build and push next)
  3  src/page.html already matches the artifact; nothing to do
  4  the artifact is older than the latest completed trading day; wait and read it again
  1  anything else (page malformed, checks failed)
"""
import io, json, os, re, subprocess, sys, urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.stdout.reconfigure(encoding='utf-8')
src = sys.argv[1]
dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'page.html')
NY = ZoneInfo('America/New_York')

# Strip the publish skeleton (one or more copies) that an artifact read wraps around the page
lines = io.open(src, encoding='utf-8').read().split('\n')
while lines and lines[0].lower().startswith('<!doctype'):
    lines = lines[1:]
text = '\n'.join(lines).rstrip()
while text.endswith('</body></html>'):
    text = text[:-len('</body></html>')].rstrip()
text += '\n'

m = re.search(r'^const QD=(\{.*?\});\s*$', text, re.M)
if not m:
    sys.exit('artifact page has no QD data; is this the digest page?')
page_date = json.loads(m.group(1))['d'][-1]

# Latest completed trading day: last S&P 500 daily bar on or before the cutoff
now = datetime.now(NY)
cutoff = now.date() if now.hour * 60 + now.minute >= 16 * 60 + 30 else now.date() - timedelta(days=1)
req = urllib.request.Request('https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?range=1mo&interval=1d',
                             headers={'User-Agent': 'Mozilla/5.0'})
r = json.load(urllib.request.urlopen(req, timeout=20))['chart']['result'][0]
days = [datetime.fromtimestamp(ts, NY).date().isoformat()
        for ts, c in zip(r['timestamp'], r['indicators']['quote'][0]['close']) if c is not None]
latest = max(d for d in days if d <= cutoff.isoformat())
print('latest completed trading day: %s | artifact page covers: %s' % (latest, page_date))

if page_date < latest:
    print('artifact not updated yet')
    sys.exit(4)

old = io.open(dst, encoding='utf-8').read() if os.path.exists(dst) else ''
if old.replace('\r\n', '\n') == text:
    print('src/page.html already matches the artifact')
    sys.exit(3)

tmp = dst + '.new'
io.open(tmp, 'w', encoding='utf-8', newline='\n').write(text)
check = subprocess.run([sys.executable, '-I', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'check_page.py'), tmp])
if check.returncode:
    os.remove(tmp)
    sys.exit('page checks failed; src/page.html left unchanged')
os.replace(tmp, dst)
print('src/page.html updated to the %s digest' % page_date)

# Record the day in data/history.json for the App's history panel (same as running tools/history.py)
here = os.path.dirname(os.path.abspath(__file__))
hist = subprocess.run([sys.executable, '-I', os.path.join(here, 'history.py'), dst,
                       os.path.join(os.path.dirname(os.path.abspath(dst)), '..', 'data', 'history.json')])
if hist.returncode:
    print('warning: history.py failed; run it again before committing')
