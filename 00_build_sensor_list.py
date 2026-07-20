'''
00_build_sensor_list.py
Look inside the glider binaries and write sensor_list.txt containing ONLY
sensors that actually carry data (non-empty time series) - not just the ones
declared in the .cac cache files.

Run this whenever you get data from a new glider or change what it logs.
Everything is configured in config.py (GLIDER, REALTIME) - nothing to edit
here unless you want to change the WISHLIST.
'''
#%% ---------------- settings ----------------
import config

DATA_DIR = None      # None = newest folder in data/ ; or Path('./data/xxx')
N_SAMPLE = 8         # how many files to probe per type (spread over deployment)

# sensors you'd LIKE to have if the glider logs them
WISHLIST = [
    'm_battpos', 'c_battpos', 'm_de_oil_vol', 'c_de_oil_vol',
    'm_fin', 'c_fin', 'c_heading', 'm_altitude', 'm_water_depth',
    'm_final_water_vx', 'm_final_water_vy', 'm_water_vx', 'm_water_vy',
    'c_wpt_lat', 'c_wpt_lon',
]

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
print(f'glider   : {config.GLIDER}')
print(f'mode     : {"realtime" if config.REALTIME else "recovered"} '
      f'({config.GLIDERSUFFIX}/{config.SCISUFFIX})')


def find_files(ext):
    files = sorted(DATA_DIR.glob(f'*.{ext}')) + sorted(DATA_DIR.glob(f'*.{ext.upper()}'))
    return files


def sample(files):
    if len(files) <= N_SAMPLE:
        return files
    idx = np.unique(np.linspace(0, len(files) - 1, N_SAMPLE).astype(int))
    return [files[i] for i in idx]


def probe(files):
    '''-> (declared, populated) sensor names. "populated" means the sensor
    actually returned at least one measurement.'''
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
print(f'\ndeployment.yml asks for {len(sources)} sensors')

#%% ---------------- probe the binaries ----------------
flight = find_files(config.GLIDERSUFFIX)
sci    = find_files(config.SCISUFFIX)
print(f'\nfound {len(flight)} flight (.{config.GLIDERSUFFIX}) and '
      f'{len(sci)} science (.{config.SCISUFFIX}) files in {DATA_DIR.name}')
if not flight and not sci:
    raise SystemExit('no binaries found - check DATA_DIR / REALTIME in config.py')

print(f'\nprobing flight files:')
f_declared, f_pop = probe(sample(flight)) if flight else (set(), set())
print(f'\nprobing science files:')
s_declared, s_pop = probe(sample(sci)) if sci else (set(), set())

populated = f_pop | s_pop
declared  = f_declared | s_declared
print(f'\n{len(declared)} sensors declared, {len(populated)} actually have data')

#%% ---------------- write sensor_list.txt ----------------
wanted = set(sources) | set(WISHLIST) | set(CORE)
keep = sorted(wanted & populated)
config.SENSORLIST.write_text('\n'.join(keep) + '\n')
print(f'\nwrote {config.SENSORLIST.name} with {len(keep)} sensors:')
for s in keep:
    print(f'  {s}')

#%% ---------------- report ----------------
dead = sorted(set(sources) - populated)
print('\n--- deployment.yml wants these but they have NO data ---')
print('    (01 will skip them automatically, no need to edit the yml)')
for s in dead:
    why = 'declared but never logged' if s in declared else 'not in this glider'
    print(f'  {s:28s} -> variable "{sources[s]}"  ({why})')
if not dead:
    print('  none - everything the yml asks for has data')

print('\n--- wishlist ---')
for s in WISHLIST:
    print(f'  {s:28s} {"HAS DATA" if s in populated else "no data"}')

extra = sorted(p for p in populated - wanted if p.startswith('sci_'))
print('\n--- other science sensors with data (you could add these to deployment.yml) ---')
for s in extra:
    print(f'  {s}')

# %%
