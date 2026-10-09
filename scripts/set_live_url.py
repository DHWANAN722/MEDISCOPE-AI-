"""Insert the actual deployed Streamlit URL into README.md. Does not deploy anything."""
import sys,re
from pathlib import Path
from urllib.parse import urlparse
if len(sys.argv)!=2:raise SystemExit('Usage: python scripts/set_live_url.py https://YOUR-ACTUAL-APP.streamlit.app')
url=sys.argv[1].strip();p=urlparse(url)
if p.scheme!='https' or not p.hostname or not p.hostname.endswith('.streamlit.app') or p.username or p.password or p.query or p.fragment:
 raise SystemExit('Use the public HTTPS Streamlit app URL, without credentials or query parameters.')
path=Path(__file__).resolve().parents[1]/'README.md';text=path.read_text()
text,n=re.subn(r'<!-- LIVE_APP_START -->.*?<!-- LIVE_APP_END -->',f'<!-- LIVE_APP_START -->\n**Live dashboard:** [Open MediScope]({url})\n<!-- LIVE_APP_END -->',text,flags=re.S)
if n!=1:raise SystemExit('Could not find exactly one live-app section.')
path.write_text(text);print('README updated with the URL you provided. Commit this README to GitHub.')
