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
}

SHARED = ['data', 'data/bathymetry_xyz', 'data/bathymetry_image', 'logs']

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
        r = subprocess.run([sys.executable, '-c', 'import config'],
                           env=env, capture_output=True, text=True)
        if r.returncode:
            ok = False
            print(f'  {g}: config.py FAILED\n{r.stdout}{r.stderr}')
        else:
            print(f'  {g}: folders ready ({PER_GLIDER_NOTE})')


#%% ============================================================
#   4. per-glider inputs
#   ============================================================
hdr('4. per-glider inputs')
for g in gliders:
    print(f'  [{g}]')

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

    sl = ROOT / f'sensor_list_{g}.txt'
    if sl.exists():
        n = len([x for x in sl.read_text().split() if x])
        print(f'    ok       {sl.name} ({n} sensors)')
    else:
        print(f'    todo     {sl.name} - run:  '
              f'GLIDER={g} python 00_build_sensor_list.py')

    dirs = [d for d in (ROOT / 'data').iterdir()
            if d.is_dir() and g.lower() in d.name.lower()]
    if dirs:
        n = sum(len(list(d.glob('*.[st]bd'))) + len(list(d.glob('*.[de]bd')))
                for d in dirs)
        print(f'    ok       {len(dirs)} download folder(s), ~{n} binaries')
    else:
        ok = False
        print(f'    MISSING  no folder in data/ with "{g}" in its name.')
        print(f'             Copy the dockserver folder in as it comes:')
        print(f'             data/{g}-from-glider-<timestamp>/')


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
    print('\n  set GLIDERS in run_gliders.py to the list above.')

print()

# %%