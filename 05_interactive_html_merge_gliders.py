'''
05_all_gliders.py
One landing page - interactive/all_gliders.html - with a button per glider.
Each glider's existing page is loaded in an iframe the first time you click
it, so this file stays a few kB instead of a few hundred MB, and switching
back is instant because loaded pages are kept alive.

Run 04_interactive_html.py for each glider first.

    python 05_all_gliders.py
'''
#%% ---------------- settings ----------------
import config

GLIDERS = None          # None = every glider with a deployment_<name>.yml
                        # that already has a page. Or fix the order:
                        # ['selkie', 'unit_1272']

TITLE    = 'All gliders'
OUT_NAME = 'all_gliders.html'
DEFAULT  = None         # glider shown on open; None = the first one
SHOW_META = True        # print size + build time of each page under the tabs

#%% ---------------- collect the pages ----------------
from pathlib import Path
import datetime as dt

HTML_ROOT = config.HTML.parent          # interactive/  (config.HTML is per glider)
OUT = HTML_ROOT / OUT_NAME


def known_gliders():
    return sorted(p.stem.replace('deployment_', '')
                  for p in config.ROOT.glob('deployment_*.yml'))


names = list(GLIDERS) if GLIDERS else known_gliders()

pages, missing = [], []
for g in names:
    p = HTML_ROOT / g / f'{g}.html'
    if not p.exists():
        missing.append(g)
        continue
    st = p.stat()
    pages.append(dict(
        glider=g,
        rel=f'{g}/{g}.html',            # relative -> the folder stays movable
        mb=st.st_size / 1e6,
        when=dt.datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M')))

for g in missing:
    print(f'  no page yet for {g}  ->  GLIDER={g} python 04_interactive_html.py')
if not pages:
    raise SystemExit(f'no glider pages under {HTML_ROOT} - run 04 first')

start = 0
if DEFAULT:
    start = next((i for i, p in enumerate(pages) if p['glider'] == DEFAULT), 0)

#%% ---------------- build the shell ----------------
PAGE = '''<!doctype html><html><head><meta charset="utf-8">
<title>@@title@@</title>
<style>
 :root{--bg:#fafafa;--fg:#222;--hdr:#12354f;--nav:#e8ecef;--hint:#666}
 html,body{height:100%;margin:0}
 body{font-family:system-ui,sans-serif;background:var(--bg);color:var(--fg);
   display:flex;flex-direction:column}
 header{padding:12px 20px;background:var(--hdr);color:#fff;flex:0 0 auto}
 header h1{margin:0;font-size:18px}
 header .meta{font-size:12.5px;opacity:.85;margin-top:3px}
 header a{color:#9fd0ff}
 nav{display:flex;gap:2px;background:var(--nav);padding:0 14px;flex:0 0 auto;
   align-items:center;flex-wrap:wrap}
 nav button{border:0;padding:11px 20px;background:none;cursor:pointer;
   font-size:14px;border-bottom:3px solid transparent;color:var(--fg)}
 nav button.on{background:var(--bg);border-bottom-color:#4da3ff;font-weight:600}
 nav .info{margin-left:auto;font-size:12px;color:var(--hint);padding-right:6px}
 .frames{flex:1 1 auto;position:relative}
 iframe{position:absolute;inset:0;width:100%;height:100%;border:0;display:none;
   background:var(--bg)}
 iframe.on{display:block}
 .note{position:absolute;inset:0;display:flex;align-items:center;
   justify-content:center;color:var(--hint);font-size:14px;text-align:center;
   padding:0 30px;line-height:1.5}
</style></head><body>
<header>
  <h1>@@title@@</h1>
  <div class="meta">@@n@@ gliders &nbsp;|&nbsp; index built @@built@@
    &nbsp;|&nbsp; <span id="meta"></span></div>
</header>
<nav>@@buttons@@<span class="info" id="link"></span></nav>
<div class="frames">
  <div class="note" id="note">loading @@first@@ ...</div>
  @@frames@@
</div>
<script>
 const PAGES = @@pages@@;
 function show(i){
   const f = document.getElementById('f' + i);
   if(!f.dataset.loaded){
     document.getElementById('note').style.display = 'flex';
     document.getElementById('note').textContent = 'loading ' + PAGES[i].glider
       + ' (' + PAGES[i].mb.toFixed(0) + ' MB) ...';
     f.addEventListener('load', () => {
       document.getElementById('note').style.display = 'none';
     }, {once:true});
     f.src = f.dataset.src;
     f.dataset.loaded = '1';
   }
   document.querySelectorAll('iframe').forEach((x,k)=>x.classList.toggle('on',k==i));
   document.querySelectorAll('nav button').forEach((x,k)=>x.classList.toggle('on',k==i));
   document.getElementById('meta').textContent = PAGES[i].meta;
   document.getElementById('link').innerHTML =
     '<a href="' + PAGES[i].rel + '" target="_blank">open ' + PAGES[i].glider
     + ' in a new tab</a>';
   location.hash = PAGES[i].glider;
 }
 const want = PAGES.findIndex(p => p.glider === location.hash.slice(1));
 show(want >= 0 ? want : @@start@@);
</script></body></html>'''

import json

buttons = ''.join(
    f'<button onclick="show({i})">{p["glider"]}</button>'
    for i, p in enumerate(pages))

frames = '\n  '.join(
    f'<iframe id="f{i}" data-src="{p["rel"]}" title="{p["glider"]}"></iframe>'
    for i, p in enumerate(pages))

js_pages = json.dumps([
    dict(glider=p['glider'], rel=p['rel'], mb=round(p['mb'], 1),
         meta=(f'{p["mb"]:.0f} MB, built {p["when"]}' if SHOW_META else ''))
    for p in pages])

html = PAGE
for k, v in (('title', TITLE),
             ('n', len(pages)),
             ('built', dt.datetime.now().strftime('%Y-%m-%d %H:%M')),
             ('first', pages[start]['glider']),
             ('buttons', buttons),
             ('frames', frames),
             ('pages', js_pages),
             ('start', start)):
    html = html.replace(f'@@{k}@@', str(v))

OUT.write_text(html)
print(f'\n{len(pages)} gliders: {", ".join(p["glider"] for p in pages)}')
print(f'-> {OUT}  ({OUT.stat().st_size/1e3:.0f} kB)')

# %%