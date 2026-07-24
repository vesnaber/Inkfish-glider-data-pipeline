'''
fresh_start.py
Run this first after cloning. It creates every folder the pipeline needs,
checks the dependencies, and tells you exactly what is still missing before
the first real run.

Changes nothing that already exists - safe to run any time.

    python fresh_start.py
'''
#%% ============================================================
#   what a working setup needs
#   ============================================================
from pathlib import Path
import importlib
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parent

REQUIRED = ['numpy', 'xarray', 'yaml', 'plotly', 'pyglider', 'dbdreader']
OPTIONAL = {
    'cmocean': 'ocean colour maps (falls back to Viridis)',
    'gsw':     'salinity + potential density (those panels vanish without it)',
    'pandas':  'much faster reading of the bathymetry grid',
    'netCDF4': 'netcdf engine for xarray',
    'pyarrow': 'parquet from 03_parse_logs.py (falls back to CSV without it)',
}

SHARED = ['data', 'data/bathymetry_xyz', 'data/bathymetry_image',
          'logs']              # 'logs' is THIS pipeline's own log output.
                               # The glider's surface dialogs go in
                               # data/<glider>-logs/, made per glider below.

PER_GLIDER_NOTE = ('cache, rawnc/segments, rawnc/merged, L0-timeseries, '
                   'L0-profiles, L0-gridfiles, plots, interactive, .state')

ok = True


def hdr(t):
    print(f'\n{t}\n' + '-' * len(t))


#%% ============================================================
#   1. python packages
#   ============================================================
hdr('1. python packages')
missing = []
for m in REQUIRED:
    try:
        importlib.import_module(m)
        print(f'  ok       {m}')
    except ImportError:
        print(f'  MISSING  {m}')
        missing.append(m)

for m, why in OPTIONAL.items():
    try:
        importlib.import_module(m)
        print(f'  ok       {m}')
    except ImportError:
        print(f'  absent   {m:12s} - {why}')

if missing:
    ok = False
    print('\n  install everything with:')
    print('    conda create -n gliderwork python=3.12')
    print('    conda activate gliderwork')
    print('    conda install -c conda-forge pyglider dbdreader cmocean gsw '
          'plotly netcdf4')

print(f'\n  python {sys.version.split()[0]} at {sys.executable}')


#%% ============================================================
#   2. shared folders
#   ============================================================
hdr('2. shared folders')
for d in SHARED:
    p = ROOT / d
    existed = p.exists()
    p.mkdir(parents=True, exist_ok=True)
    print(f'  {"kept  " if existed else "made  "} {d}/')


#%% ============================================================
#   3. which gliders are configured
#   ============================================================
hdr('3. gliders')
ymls = sorted(ROOT.glob('deployment_*.yml'))
gliders = [p.stem.replace('deployment_', '') for p in ymls]

# config decides where the data lives (vm vs local layout, GLIDER_DATA_ROOT,
# deployment_start), and it reads the environment at import time - so ask it
# once per glider in its own process instead of guessing paths here.
PROBE = '''
import json, config
print("@@" + json.dumps(dict(
    layout=config.LAYOUT, realtime=config.REALTIME,
    data_root=str(config.DATA_ROOT),
    inbox=str(config.glider_inbox()), logs=str(config.glider_logs_dir()),
    flight=config.GLIDERSUFFIX, sci=config.SCISUFFIX,
    start=str(config.deployment_start()),
    filt=config.FILE_FILTER, cache=str(config.CACHE))))
'''

info = {}
if not gliders:
    ok = False
    print('  NO deployment_<glider>.yml found.')
    print('  Copy the example one, rename it deployment_<yourglider>.yml,')
    print('  and edit the metadata block (glider_name must match the file')
    print('  name) plus the netcdf_variables sources.')
else:
    print(f'  found: {", ".join(gliders)}')
    for g in gliders:
        env = {**os.environ, 'GLIDER': g}
        r = subprocess.run([sys.executable, '-c', PROBE],
                           env=env, capture_output=True, text=True)
        if r.returncode:
            ok = False
            print(f'  {g}: config.py FAILED\n{r.stdout}{r.stderr}')
            continue
        import json
        line = next((l for l in r.stdout.splitlines()
                     if l.startswith('@@')), None)
        info[g] = json.loads(line[2:]) if line else {}
        i = info[g]
        print(f'  {g}: layout {i["layout"]} '
              f'({"realtime " + i["flight"] + "/" + i["sci"] if i["realtime"] else "recovered " + i["flight"] + "/" + i["sci"]})'
              f', folders ready ({PER_GLIDER_NOTE})')


#%% ============================================================
#   4. per-glider inputs
#   ============================================================
hdr('4. per-glider inputs')
for g in gliders:
    print(f'  [{g}]')
    i = info.get(g, {})

    yml = ROOT / f'deployment_{g}.yml'
    try:
        import yaml
        dep = yaml.safe_load(yml.read_text())
        name = dep.get('metadata', {}).get('glider_name', '?')
        flag = '' if name == g else f'   <-- says "{name}", should be "{g}"'
        print(f'    ok       {yml.name}{flag}')
        if flag:
            ok = False
    except Exception as e:
        ok = False
        print(f'    BROKEN   {yml.name}: {e}')

    start = i.get('start', 'None')
    if start in ('None', '', None):
        ok = False
        print(f'    MISSING  deployment_start: in {yml.name} - without it '
              f'every old mission\n'
              f'             still in the folder is processed. Add it under '
              f'metadata:')
    else:
        print(f'    ok       deployment_start {start[:16]}'
              + ('' if i.get('filt', True)
                 else '   (GLIDER_FILE_FILTER=0: filter OFF)'))

    sl = ROOT / f'sensor_list_{g}.txt'
    if sl.exists():
        n = len([x for x in sl.read_text().split() if x])
        print(f'    ok       {sl.name} ({n} sensors)')
    else:
        print(f'    todo     {sl.name} - run:  '
              f'GLIDER={g} python 00_build_sensor_list.py')

    # the inbox is wherever config says it is: inside the repo on a laptop,
    # out under ~/data/rt-data on the VM. Guessing a repo path here is what
    # made this section lie about the VM.
    inbox = Path(i['inbox']) if i.get('inbox') else ROOT / 'data' / f'{g}-from-glider'
    flight, sci = i.get('flight', 'sbd'), i.get('sci', 'tbd')

    def _count(d, ext):
        if not d.exists():
            return 0
        return len({p.resolve() for pat in (f'*.{ext}', f'*.{ext.upper()}')
                    for p in d.glob(pat)})

    n_fl, n_sc = _count(inbox, flight), _count(inbox, sci)
    if not inbox.exists():
        ok = False
        print(f'    MISSING  {inbox}  - the inbox does not exist')
        if i.get('layout') == 'vm':
            print(f'             layout is "vm", so this folder belongs to '
                  f'the ingestion service.\n'
                  f'             Wrong machine? The laptop layout is '
                  f'REALTIME=0.')
    elif not (n_fl or n_sc):
        ok = False
        print(f'    EMPTY    {inbox}  - binaries go here')
    else:
        print(f'    ok       {inbox}')
        print(f'             {n_fl} *.{flight} (flight), '
              f'{n_sc} *.{sci} (science)')
        if not n_sc:
            ok = False
            print(f'             !! no science files - the merge cannot '
                  f'produce anything.\n'
                  f'                GLIDER={g} python diagnose_binaries.py')

    # accepted after the name + deployment_start filter
    if n_fl or n_sc:
        env = {**os.environ, 'GLIDER': g}
        code = ('import config;'
                f'print("@@", len(config.binaries_in(config.glider_inbox(),'
                f' config.GLIDERSUFFIX)),'
                f' len(config.binaries_in(config.glider_inbox(),'
                f' config.SCISUFFIX)))')
        r = subprocess.run([sys.executable, '-c', code], env=env,
                           capture_output=True, text=True)
        line = next((l for l in r.stdout.splitlines()
                     if l.startswith('@@')), None)
        if line:
            a_fl, a_sc = (int(x) for x in line.split()[1:3])
            print(f'    ok       accepted by the filter: {a_fl} {flight}, '
                  f'{a_sc} {sci}'
                  + ('   <-- everything filtered out!'
                     if not (a_fl or a_sc) else ''))
            if not (a_fl or a_sc):
                ok = False

    lg = Path(i['logs']) if i.get('logs') else ROOT / 'data' / f'{g}-logs'
    logs = ([p for p in lg.rglob('*')
             if p.is_file() and not p.name.startswith('.')]
            if lg.exists() else [])
    if logs:
        mb = sum(p.stat().st_size for p in logs) / 1e6
        print(f'    ok       {lg}  ({len(logs)} files, {mb:.1f} MB)')
    else:
        print(f'    empty    {lg}  - surface dialogs go here (optional; '
              f'without them the Logs/Battery tabs are skipped)')

    cache = Path(i['cache']) if i.get('cache') else ROOT / 'cache' / g
    n_cac = len(list(cache.glob('*.cac'))) + len(list(cache.glob('*.CAC')))
    print(f'    {"ok      " if n_cac else "empty   "} {cache}  '
          f'({n_cac} *.cac)')
    if not n_cac:
        print(f'             realtime {sci}/{flight} files need the '
              f'dockserver cache to be readable.\n'
              f'             GLIDER={g} python diagnose_binaries.py  '
              f'finds and copies them.')


#%% ============================================================
#   5. bathymetry (optional, shared by every glider)
#   ============================================================
hdr('5. bathymetry (optional)')
try:
    import config
    xyz = config.find_bathy_xyz(verbose=False)
    print(f'  {"ok      " if xyz else "absent  "} data/bathymetry_xyz/'
          f'{"  " + xyz.name if xyz else ""}')
    if not xyz:
        print('           3D tab works without it, just no seabed under the')
        print('           curtain. Drop an ASCII "lon lat depth" grid in')
        print('           (.xyz/.txt/.asc), depth negative downward.')

    img = sorted(p for p in config.BATHY_IMG_DIR.iterdir()
                 if p.suffix.lower() in config.IMG_SUFFIXES)
    if not img:
        print('  absent   data/bathymetry_image/')
        print('           Map tab works without it - you get the plain')
        print('           basemap. To add one, drop in a georeferenced image')
        print('           plus a bounds sidecar (see below).')
    else:
        b = config.read_bounds(img[0])
        if b:
            print(f'  ok       data/bathymetry_image/  {img[0].name}')
            print(f'           bounds S {b[0]} W {b[1]} N {b[2]} E {b[3]}')
        else:
            ok = False
            print(f'  BOUNDS   {img[0].name} has no bounds sidecar.')
            print(f'           Create data/bathymetry_image/'
                  f'{img[0].stem}.bounds containing one line:')
            print(f'               south west north east')
            print(f'           e.g. 11.911967 -69.244978 '
                  f'12.451538 -68.610832')
except Exception as e:
    print(f'  could not check: {e}')


#%% ============================================================
#   6. what to do next
#   ============================================================
hdr('6. next')
if not gliders:
    print('  1. write deployment_<glider>.yml')
    print('  2. put the download folder in data/')
    print('  3. run fresh_start.py again')
elif not ok:
    print('  fix what is marked MISSING, BROKEN or BOUNDS above, then rerun.')
else:
    for g in [x for x in gliders
              if not (ROOT / f'sensor_list_{x}.txt').exists()]:
        print(f'  GLIDER={g} python 00_build_sensor_list.py')
    print('  python run_gliders.py        # all gliders, all steps')
    print('  (or one at a time: GLIDER=<name> python 01_process_to_nc.py)')
    if any((ROOT / 'data' / f'{g}-logs').exists()
           and any((ROOT / 'data' / f'{g}-logs').iterdir()) for g in gliders):
        print('  GLIDER=<name> python 03_parse_logs.py   # surface dialogs')
    print('\\n  set GLIDERS in run_gliders.py to the list above.')

print()

# %%