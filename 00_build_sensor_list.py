'''
00_build_sensor_list.py
Look inside the glider binaries and write sensor_list_<glider>.txt containing
ONLY sensors that actually carry data (non-empty time series) - not just the
ones declared in the .cac cache files.

One list per glider, next to deployment_<glider>.yml. Run this whenever you
get data from a new glider or change what it logs.

Everything is configured in config.py (GLIDER, REALTIME). Per-glider sensor
wishes go in WISHLIST_EXTRA below.
'''
#%% ---------------- settings ----------------
import config

DATA_DIR = None      # None = newest folder in data/ for this glider
N_SAMPLE = 8         # files to probe per type (spread over the deployment)

# sensors you'd LIKE on every glider, if it logs them
WISHLIST = [
    'm_battpos', 'c_battpos', 'm_de_oil_vol', 'c_de_oil_vol',
    'm_fin', 'c_fin', 'c_heading', 'm_altitude', 'm_water_depth',
    'm_final_water_vx', 'm_final_water_vy', 'm_water_vx', 'm_water_vy',
    'c_wpt_lat', 'c_wpt_lon',
]

# extra wishes for specific gliders (different payloads)
WISHLIST_EXTRA = {
    # 'selkie':    ['sci_suna_nitrate_concentration'],
    # 'unit_1272': ['sci_flbbcd_cdom_units'],
}

# sensors pyglider needs (kept only if actually populated)
CORE = [
    'm_present_time', 'sci_m_present_time',
    'm_lat', 'm_lon', 'm_gps_lat', 'm_gps_lon',
    'm_depth', 'm_pressure', 'sci_water_pressure',
    'sci_water_temp', 'sci_water_cond',
    'm_pitch', 'm_roll', 'm_heading',
]

#%% ---------------- setup ----------------
from pathlib import Path
import numpy as np
import yaml
import dbdreader

DATA_DIR = Path(DATA_DIR) if DATA_DIR else config.latest_data_dir()
wishlist = WISHLIST + WISHLIST_EXTRA.get(config.GLIDER, [])

print(f'glider   : {config.GLIDER}')
print(f'mode     : {"realtime" if config.REALTIME else "recovered"} '
      f'({config.GLIDERSUFFIX}/{config.SCISUFFIX})')
print(f'writing  : {config.SENSORLIST.name}')


def sample(files):
    if len(files) <= N_SAMPLE:
        return files
    idx = np.unique(np.linspace(0, len(files) - 1, N_SAMPLE).astype(int))
    return [files[i] for i in idx]


def probe(files):
    '''-> (declared, populated) sensor names. "populated" = the sensor
    returned at least one measurement.'''
    declared, populated = set(), set()
    for f in files:
        try:
            dbd = dbdreader.DBD(str(f), cacheDir=str(config.CACHE))
        except Exception as e:
            print(f'  could not open {f.name}: {e}')
            continue
        names = list(dbd.parameterNames)
        declared |= set(names)
        for p in set(names) - populated:
            try:
                t, _ = dbd.get(p)
                if np.size(t) > 0:
                    populated.add(p)
            except Exception:
                pass
        try:
            dbd.close()
        except Exception:
            pass
        print(f'  {f.name}: {len(populated)} sensors with data so far')
    return declared, populated

#%% ---------------- what does deployment.yml ask for? ----------------
dep = yaml.safe_load(config.DEPLOYMENT.read_text())
sources = {}
for section in ('netcdf_variables', 'profile_variables'):
    for var, spec in (dep.get(section) or {}).items():
        if isinstance(spec, dict) and 'source' in spec:
            sources[spec['source']] = var
print(f'\n{config.DEPLOYMENT.name} asks for {len(sources)} sensors')

#%% ---------------- probe the binaries ----------------
flight = config.binaries_in(DATA_DIR, config.GLIDERSUFFIX)
sci    = config.binaries_in(DATA_DIR, config.SCISUFFIX)
print(f'\nfound {len(flight)} flight (.{config.GLIDERSUFFIX}) and '
      f'{len(sci)} science (.{config.SCISUFFIX}) files in {DATA_DIR.name}')
if not flight and not sci:
    raise SystemExit('no binaries found - check DATA_DIR / REALTIME in config.py')

print('\nprobing flight files:')
f_declared, f_pop = probe(sample(flight)) if flight else (set(), set())
print('\nprobing science files:')
s_declared, s_pop = probe(sample(sci)) if sci else (set(), set())

populated = f_pop | s_pop
declared  = f_declared | s_declared
print(f'\n{len(declared)} sensors declared, {len(populated)} actually have data')

#%% ---------------- write sensor_list_<glider>.txt ----------------
wanted = set(sources) | set(wishlist) | set(CORE)
keep = sorted(wanted & populated)

old = (set(config.SENSORLIST.read_text().split())
       if config.SENSORLIST.exists() else set())
added, removed = sorted(set(keep) - old), sorted(old - set(keep))

config.SENSORLIST.write_text('\n'.join(keep) + '\n')
print(f'\nwrote {config.SENSORLIST.name} with {len(keep)} sensors')

if not old:
    print('  (new list)')
elif added or removed:
    for s in added:
        print(f'  + {s}')
    for s in removed:
        print(f'  - {s}')
    print('\n!! the sensor list CHANGED -> 01 will rebuild rawnc from the\n'
          '   binaries for this glider (the slow step). That is intended:\n'
          '   the converted files no longer match the requested sensors.')
else:
    print('  (unchanged - 01 will not redo any work)')

#%% ---------------- report ----------------
dead = sorted(set(sources) - populated)
print('\n--- deployment.yml wants these but they have NO data ---')
print('    (01 skips them automatically, no need to edit the yml)')
for s in dead:
    why = 'declared but never logged' if s in declared else 'not in this glider'
    print(f'  {s:28s} -> variable "{sources[s]}"  ({why})')
if not dead:
    print('  none - everything the yml asks for has data')

print('\n--- wishlist ---')
for s in wishlist:
    print(f'  {s:28s} {"HAS DATA" if s in populated else "no data"}')

extra = sorted(p for p in populated - wanted if p.startswith('sci_'))
print('\n--- other science sensors with data '
      '(candidates for deployment.yml) ---')
for s in extra:
    print(f'  {s}')
if not extra:
    print('  none')

# %%