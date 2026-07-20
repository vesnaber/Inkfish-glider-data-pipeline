'''
01_process_to_nc.py
Binaries -> netcdf, using pyglider.

  binaries -> rawnc -> L0-timeseries -> L0-profiles -> L0-gridfiles
                                                    -> plots/preliminary_data.png

Robust by design:
- glider name / realtime-vs-recovered / paths all come from config.py
- newest folder in data/ is used automatically (override with DATA_DIR below)
- sensors listed but absent from the data are DROPPED WITH A WARNING instead
  of crashing; same for deployment.yml variables whose source has no data
- old outputs are deleted first so you never plot a stale file
'''
#%% ---------------- settings ----------------
import config

DATA_DIR  = None    # None = newest folder in data/ ; or './data/selkie-...'
OVERWRITE = True    # True = delete old nc first (recommended)

PROFILE_FILT_TIME = 20    # s, smoothing for profile detection
PROFILE_MIN_TIME  = 300    # s, shortest thing that counts as a profile

# quick look plot made at the end
PRELIM_VARS = ['temperature', 'conductivity', 'oxygen_concentration',
               'chlorophyll']
PRELIM_NAME = 'preliminary_data.png'

#%% ---------------- setup ----------------
from pathlib import Path
import logging
import shutil
import yaml

import pyglider.slocum as slocum
import pyglider.ncprocess as ncprocess
import pyglider.utils as pgutils

logging.basicConfig(level='INFO')

DATA_DIR = Path(DATA_DIR) if DATA_DIR else config.latest_data_dir()
print(f'\nglider : {config.GLIDER}')
print(f'mode   : {"realtime" if config.REALTIME else "recovered (full res)"} '
      f'({config.GLIDERSUFFIX}/{config.SCISUFFIX})')
print(f'data   : {DATA_DIR}')

dep = yaml.safe_load(config.DEPLOYMENT.read_text())
yml_name = dep.get('metadata', {}).get('glider_name', '?')
if yml_name != config.GLIDER:
    print(f'\n!! config.GLIDER = "{config.GLIDER}" but deployment.yml says '
          f'"{yml_name}". Output files will be named after the yml. '
          f'Make them match to avoid confusion.\n')

if OVERWRITE:
    config.clear_outputs()

#%% ---------------- check which sensors really exist in this data ----------------
# Anything in sensor_list.txt that is missing from the binaries would make
# pyglider fail later, so we filter it out here and just report it.
import dbdreader

wanted = [ln.strip() for ln in config.SENSORLIST.read_text().splitlines()
          if ln.strip() and not ln.startswith('#')]

available = set()
for ext in (config.GLIDERSUFFIX, config.SCISUFFIX):
    files = sorted(DATA_DIR.glob(f'*.{ext}')) + sorted(DATA_DIR.glob(f'*.{ext.upper()}'))
    for f in files[:5]:                     # a few files are enough
        try:
            d = dbdreader.DBD(str(f), cacheDir=str(config.CACHE))
            available |= set(d.parameterNames)
            d.close()
        except Exception as e:
            print(f'  could not read {f.name}: {e}')

if available:
    usable  = [s for s in wanted if s in available]
    dropped = [s for s in wanted if s not in available]
    if dropped:
        print(f'\nNOT in this dataset, skipping ({len(dropped)}): '
              f'{", ".join(dropped)}')
        print('   (rerun 00_build_sensor_list.py to refresh sensor_list.txt)')
else:
    print('\ncould not inspect binaries - using sensor_list.txt as is')
    usable = wanted

SENSORS_USED = config.ROOT / 'sensor_list_used.txt'
SENSORS_USED.write_text('\n'.join(usable) + '\n')
print(f'using {len(usable)} sensors -> {SENSORS_USED.name}')

#%% ---------------- drop yml variables whose sensor is missing ----------------
# Writes a temporary yml so the original deployment.yml stays untouched.
missing_vars = {v: spec['source']
                for v, spec in (dep.get('netcdf_variables') or {}).items()
                if isinstance(spec, dict) and 'source' in spec
                and spec['source'] not in usable}

DEPLOY_USED = config.DEPLOYMENT
if missing_vars:
    print(f'\nvariables with no sensor data, leaving them out ({len(missing_vars)}):')
    for v, s in missing_vars.items():
        print(f'  {v:28s} (needs {s})')
    dep2 = dict(dep)
    dep2['netcdf_variables'] = {k: v for k, v in dep['netcdf_variables'].items()
                                if k not in missing_vars}
    DEPLOY_USED = config.ROOT / 'deployment_used.yml'
    DEPLOY_USED.write_text(yaml.safe_dump(dep2, sort_keys=False))
    print(f'  -> using {DEPLOY_USED.name} for this run '
          f'(your deployment.yml is unchanged)')

#%% ---------------- binaries -> rawnc ----------------
if OVERWRITE and config.RAWNC.exists():
    shutil.rmtree(config.RAWNC); config.RAWNC.mkdir()

print('\nSTEP 1/5  reading binaries...')
slocum.binary_to_rawnc(
    str(DATA_DIR) + '/', str(config.RAWNC) + '/', str(config.CACHE) + '/',
    str(SENSORS_USED), str(DEPLOY_USED),
    incremental=not OVERWRITE,
    scisuffix=config.SCISUFFIX, glidersuffix=config.GLIDERSUFFIX)


#%% ---------------- merge ----------------
print('\nSTEP 2/5  merging segments...')
slocum.merge_rawnc(
    str(config.RAWNC) + '/', str(config.RAWNC) + '/', str(DEPLOY_USED),
    scisuffix=config.SCISUFFIX, glidersuffix=config.GLIDERSUFFIX)

#%% ---------------- timeseries ----------------
print('\nSTEP 3/5  making the timeseries...')
tsname = slocum.raw_to_timeseries(
    str(config.RAWNC) + '/', str(config.L0_TS) + '/', str(DEPLOY_USED),
    profile_filt_time=PROFILE_FILT_TIME,
    profile_min_time=PROFILE_MIN_TIME)
print(f'  -> {tsname}')

#%% ---------------- profiles ----------------
print('\nSTEP 4/5  splitting into profiles...')
ncprocess.extract_timeseries_profiles(tsname, str(config.L0_PROFILES) + '/',
                                      str(DEPLOY_USED))

#%% ---------------- grid + quick look plot ----------------
print('\nSTEP 5/5  gridding...')
gridname = ncprocess.make_gridfiles(tsname, str(config.L0_GRID) + '/',
                                    str(DEPLOY_USED))
print(f'  -> {gridname}')

import xarray as xr
with xr.open_dataset(gridname) as g:
    have = [v for v in PRELIM_VARS if v in g]
    nprof = g.time.size
    zmax = float(g.depth.max())
print(f'\ngrid has {nprof} profiles, down to {zmax:.0f} m')
print(f'quick look plot of: {", ".join(have)}')

outpng = config.PLOTS / PRELIM_NAME
pgutils.example_gridplot(gridname, str(outpng), ylim=[None, None], toplot=have)
print(f'\nDONE. Quick look: {outpng}')
print('Now run 02_plots_full_timeseries.py for proper plots.')

# %%
