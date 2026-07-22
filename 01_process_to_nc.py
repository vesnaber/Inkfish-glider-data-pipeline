'''
01_process_to_nc.py
Binaries -> netcdf, using pyglider. Incremental: each stage is skipped when
its settings and its inputs are unchanged.

  binaries -> rawnc/segments -> rawnc/merged -> L0-timeseries -> L0-profiles
                                                              -> L0-gridfiles
                                                              -> plots/...png

Two things this handles that the naive version got wrong:

1. ALL download folders for the glider are converted, not just the newest.
   Downloads are not always cumulative, so using only the newest folder
   silently drops everything that came before.
2. merge_rawnc CONSUMES its input directory. So the per-segment files live
   in rawnc/<glider>/segments/ (an archive only this script adds to), and
   the merge runs on a disposable copy. Copying ~25 MB is far cheaper than
   re-parsing every binary on every run.

Select the glider per process:
    GLIDER=unit_1272 python 01_process_to_nc.py
'''
#%% ---------------- settings ----------------
import config

DATA_DIRS = None    # None = every download folder in data/ for THIS glider.
                    # Or a list of paths to restrict it:
                    # ['./data/selkie-from-glider-20260721T154333']

FORCE = None        # None | 'rawnc' | 'merge' | 'timeseries' | 'profiles'
                    # | 'grid' | 'all'
                    # Redo that stage and everything after it, even when
                    # nothing changed. 'rawnc' also wipes the segment
                    # archive - the slow one, avoid unless the conversion
                    # itself looks wrong.

PROFILE_FILT_TIME = 20     # s, smoothing for profile detection
PROFILE_MIN_TIME  = 300    # s, shortest thing that counts as a profile

TIMING = True       # print seconds per stage - the fastest way to see which
                    # step is actually costing you time

NEW_XARRAY_COMBINE = False
                    # True -> compat='override', join='exact' in the merge.
                    # Much faster when the segment files are homogeneous, but
                    # RAISES ValueError if they are not. Try it; if the merge
                    # blows up, your segments have mixed variable sets and
                    # want a clean rebuild instead.

PRELIM_VARS = ['temperature', 'conductivity', 'oxygen_concentration',
               'chlorophyll']
PRELIM_NAME = 'preliminary_data.png'

_ORDER = ['rawnc', 'merge', 'timeseries', 'profiles', 'grid']


def forced(stage):
    '''True if FORCE names this stage or an earlier one'''
    if not FORCE:
        return False
    if FORCE == 'all':
        return True
    return _ORDER.index(stage) >= _ORDER.index(FORCE)


#%% ---------------- setup ----------------
from pathlib import Path
import logging
import shutil
import time
import yaml

import xarray as xr
import pyglider.slocum as slocum
import pyglider.ncprocess as ncprocess
import pyglider.utils as pgutils

logging.basicConfig(level='INFO')

if NEW_XARRAY_COMBINE:
    xr.set_options(use_new_combine_kwarg_defaults=True)

_T0 = time.time()
_TPREV = _T0
_TIMES = {}


def tick(label):
    '''seconds since the previous tick'''
    global _TPREV
    now = time.time()
    _TIMES[label] = now - _TPREV
    if TIMING:
        print(f'  [{label}: {now - _TPREV:.1f} s | total {now - _T0:.1f} s]')
    _TPREV = now


data_dirs = ([Path(d) for d in DATA_DIRS] if DATA_DIRS
             else config.all_data_dirs())

print(f'\nglider : {config.GLIDER}')
print(f'mode   : {"realtime" if config.REALTIME else "recovered (full res)"} '
      f'({config.GLIDERSUFFIX}/{config.SCISUFFIX})')
print(f'sensors: {config.SENSORLIST.name}')
config.status()

if not config.SENSORLIST.exists():
    raise SystemExit(f'{config.SENSORLIST.name} is missing - run '
                     f'00_build_sensor_list.py for this glider first')

dep = yaml.safe_load(config.DEPLOYMENT.read_text())
yml_name = dep.get('metadata', {}).get('glider_name', '?')
if yml_name != config.GLIDER:
    print(f'\n!! config.GLIDER = "{config.GLIDER}" but {config.DEPLOYMENT.name} '
          f'says "{yml_name}". Output files are named after the yml.\n')


#%% ---------------- which sensors really exist in this data ----------------
# Anything in the sensor list that is missing from the binaries would make
# pyglider fail later, so filter it out here and just report it.
import dbdreader

wanted = [ln.strip() for ln in config.SENSORLIST.read_text().splitlines()
          if ln.strip() and not ln.startswith('#')]

available = set()
for ext in (config.GLIDERSUFFIX, config.SCISUFFIX):
    files = config.binaries_in(data_dirs[-1], ext)   # newest folder is enough
    for f in files[:5]:
        try:
            d = dbdreader.DBD(str(f), cacheDir=str(config.CACHE))
            available |= set(d.parameterNames)
            d.close()
        except Exception as e:
            print(f'  could not read {f.name}: {e}')

if available:
    usable = [s for s in wanted if s in available]
    dropped = [s for s in wanted if s not in available]
    if dropped:
        print(f'\nNOT in this dataset, skipping ({len(dropped)}): '
              f'{", ".join(dropped)}')
        print('   (rerun 00_build_sensor_list.py to refresh the list)')
else:
    print('\ncould not inspect binaries - using the sensor list as is')
    usable = wanted

SENSORS_USED = config.STATE / 'sensor_list_used.txt'
SENSORS_USED.write_text('\n'.join(usable) + '\n')
print(f'using {len(usable)} sensors -> {SENSORS_USED}')


#%% ---------------- drop yml variables whose sensor is missing ----------------
# Written to a temporary yml so the original deployment file stays untouched.
missing_vars = {v: spec['source']
                for v, spec in (dep.get('netcdf_variables') or {}).items()
                if isinstance(spec, dict) and 'source' in spec
                and spec['source'] not in usable}

DEPLOY_USED = config.DEPLOYMENT
if missing_vars:
    print(f'\nvariables with no sensor data, leaving them out '
          f'({len(missing_vars)}):')
    for v, s in missing_vars.items():
        print(f'  {v:28s} (needs {s})')
    dep2 = dict(dep)
    dep2['netcdf_variables'] = {k: v for k, v in dep['netcdf_variables'].items()
                                if k not in missing_vars}
    DEPLOY_USED = config.STATE / 'deployment_used.yml'
    DEPLOY_USED.write_text(yaml.safe_dump(dep2, sort_keys=False))
    print(f'  -> using {DEPLOY_USED.name} for this run '
          f'({config.DEPLOYMENT.name} unchanged)')

YML_FINGERPRINT = config._sha(yaml.safe_load(DEPLOY_USED.read_text()))
tick('setup')


#%% ---------------- STAGE 1/5  binaries -> rawnc/segments ----------------
# Settings that invalidate the converted binaries. The list of download
# folders is deliberately NOT here: a new folder should ADD segments, not
# trigger a rebuild.
K_RAW = config.stage_key('rawnc', {
    'sensors': sorted(usable),
    'yml': YML_FINGERPRINT,
    'suffixes': [config.GLIDERSUFFIX, config.SCISUFFIX],
})
rebuild_raw, why = config.needs_rerun('rawnc', K_RAW, force=forced('rawnc'))

print(f'\nSTEP 1/5  binaries -> segments   [{why}]')
if rebuild_raw and any(config.RAWNC_SEG.glob('*.nc')):
    print('  settings changed -> discarding the old conversion')
    shutil.rmtree(config.RAWNC_SEG)
    config.RAWNC_SEG.mkdir(parents=True)

before = config.dir_signature(config.RAWNC_SEG)
for i, d in enumerate(data_dirs, 1):
    n_before = len(list(config.RAWNC_SEG.glob('*.nc')))
    print(f'  [{i}/{len(data_dirs)}] {d.name}')
    slocum.binary_to_rawnc(
        str(d) + '/', str(config.RAWNC_SEG) + '/', str(config.CACHE) + '/',
        str(SENSORS_USED), str(DEPLOY_USED),
        incremental=not rebuild_raw,     # False only when we just wiped it
        scisuffix=config.SCISUFFIX, glidersuffix=config.GLIDERSUFFIX)
    n_after = len(list(config.RAWNC_SEG.glob('*.nc')))
    print(f'      -> {n_after - n_before} new segments '
          f'({n_after} total)')

after = config.dir_signature(config.RAWNC_SEG)
print(f'  segments: {before["n"]} -> {after["n"]} '
      f'({after["n"] - before["n"]} new)')
print(f'  signature: {after["hash"]}  '
      f'({"UNCHANGED" if after == before else "changed"})')
config.write_state('rawnc', K_RAW, **after)
tick('rawnc')

# this signature feeds every downstream key, so new segments cascade forward
RAW_SIG = after


#%% ---------------- STAGE 2/5  merge (on a disposable copy) ----------------
# merge_rawnc consumes its input directory, so it never touches the archive.
K_MERGE = config.stage_key('merge', {'yml': YML_FINGERPRINT},
                           upstream=config.stage_key('_', RAW_SIG, K_RAW))
run, why = config.needs_rerun('merge', K_MERGE, force=forced('merge'))
print(f'\nSTEP 2/5  merging segments   [{why}]')
if run:
    shutil.rmtree(config.RAWNC_WORK, ignore_errors=True)
    shutil.copytree(config.RAWNC_SEG, config.RAWNC_WORK)
    n_copy = len(list(config.RAWNC_WORK.glob('*.nc')))
    print(f'  working on a copy of {n_copy} segments')

    for f in config.RAWNC_MERGED.glob('*.nc'):     # no stale merged files
        f.unlink()

    slocum.merge_rawnc(
        str(config.RAWNC_WORK) + '/', str(config.RAWNC_MERGED) + '/',
        str(DEPLOY_USED),
        scisuffix=config.SCISUFFIX, glidersuffix=config.GLIDERSUFFIX)

    left = len(list(config.RAWNC_WORK.glob('*.nc')))
    print(f'  merge left {left}/{n_copy} of the copy '
          f'({"consumed them" if left < n_copy else "kept them"}) '
          f'- the archive is untouched either way')
    shutil.rmtree(config.RAWNC_WORK, ignore_errors=True)

    merged = sorted(p.name for p in config.RAWNC_MERGED.glob('*.nc'))
    print(f'  merged files: {", ".join(merged) if merged else "NONE"}')
    config.write_state('merge', K_MERGE,
                       **config.dir_signature(config.RAWNC_MERGED))
else:
    print('  skipped')
tick('merge')

if not any(config.RAWNC_MERGED.glob('*.nc')):
    raise SystemExit(f'no merged files in {config.RAWNC_MERGED} - '
                     f'the merge produced nothing, cannot continue')


#%% ---------------- STAGE 3/5  timeseries ----------------
K_TS = config.stage_key('timeseries', {
    'profile_filt_time': PROFILE_FILT_TIME,
    'profile_min_time': PROFILE_MIN_TIME,
    'yml': YML_FINGERPRINT,
}, upstream=K_MERGE)

tsname = config.read_state('timeseries').get('tsname')
run, why = config.needs_rerun('timeseries', K_TS, outputs=[tsname],
                              force=forced('timeseries'))
print(f'\nSTEP 3/5  timeseries   [{why}]')
if run:
    tsname = slocum.raw_to_timeseries(
        str(config.RAWNC_MERGED) + '/', str(config.L0_TS) + '/',
        str(DEPLOY_USED),
        profile_filt_time=PROFILE_FILT_TIME,
        profile_min_time=PROFILE_MIN_TIME)
    config.write_state('timeseries', K_TS, tsname=str(tsname))
else:
    print('  skipped')
print(f'  -> {tsname}')
tick('timeseries')


#%% ---------------- STAGE 4/5  profiles ----------------
K_PROF = config.stage_key('profiles', {'yml': YML_FINGERPRINT}, upstream=K_TS)
run, why = config.needs_rerun('profiles', K_PROF, force=forced('profiles'))
print(f'\nSTEP 4/5  profiles   [{why}]')
if run:
    ncprocess.extract_timeseries_profiles(
        tsname, str(config.L0_PROFILES) + '/', str(DEPLOY_USED))
    config.write_state('profiles', K_PROF,
                       **config.dir_signature(config.L0_PROFILES))
else:
    print('  skipped')
tick('profiles')


#%% ---------------- STAGE 5/5  grid ----------------
K_GRID = config.stage_key('grid', {'yml': YML_FINGERPRINT}, upstream=K_TS)

gridname = config.read_state('grid').get('gridname')
run, why = config.needs_rerun('grid', K_GRID, outputs=[gridname],
                              force=forced('grid'))
print(f'\nSTEP 5/5  gridding   [{why}]')
if run:
    gridname = ncprocess.make_gridfiles(
        tsname, str(config.L0_GRID) + '/', str(DEPLOY_USED))
    config.write_state('grid', K_GRID, gridname=str(gridname))
    config.clear_stage()                    # segment table may be stale
    (config.STATE / 'segments.csv').unlink(missing_ok=True)
    config.write_state('rawnc', K_RAW, **RAW_SIG)
    config.write_state('merge', K_MERGE,
                       **config.dir_signature(config.RAWNC_MERGED))
    config.write_state('timeseries', K_TS, tsname=str(tsname))
    config.write_state('profiles', K_PROF,
                       **config.dir_signature(config.L0_PROFILES))
    config.write_state('grid', K_GRID, gridname=str(gridname))
else:
    print('  skipped')
print(f'  -> {gridname}')
tick('grid')


#%% ---------------- quick look ----------------
with xr.open_dataset(gridname) as g:
    have = [v for v in PRELIM_VARS if v in g]
    print(f'\ngrid has {g.time.size} profiles, '
          f'down to {float(g.depth.max()):.0f} m, '
          f'{str(g.time.values[0])[:16]} to {str(g.time.values[-1])[:16]}')

outpng = config.PLOTS / PRELIM_NAME
pgutils.example_gridplot(gridname, str(outpng), ylim=[None, None], toplot=have)
tick('quicklook')

if TIMING:
    print('\ntime per stage:')
    for k, v in sorted(_TIMES.items(), key=lambda kv: -kv[1]):
        print(f'  {k:12s} {v:7.1f} s')
print(f'\nDONE ({config.GLIDER}) in {time.time() - _T0:.0f} s. '
      f'Quick look: {outpng}')

# %%