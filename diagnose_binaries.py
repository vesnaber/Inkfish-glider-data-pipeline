'''
diagnose_binaries.py
Why does one file type refuse to convert? Reads the ASCII header of a real
binary, works out which sensor-list CACHE it needs, checks whether that
cache exists, hunts for it on disk, and then tries dbdreader on the file so
the REAL exception is printed instead of pyglider's generic warning.

    GLIDER=selkie python diagnose_binaries.py
    GLIDER=selkie COPY=1 python diagnose_binaries.py   # copy caches it finds

Nothing is modified unless COPY=1.
'''
#%% ---------------- settings ----------------
import config
import os

N_SHOW = 3                                   # files to inspect per type
COPY = os.environ.get('COPY', '0') not in ('0', 'false', 'no')
SEARCH_ROOTS = ['~/data', '~/glider-app', str(config.ROOT)]

#%% ---------------- header reader ----------------
from pathlib import Path
import shutil


def header(path, nbytes=4096):
    '''The ASCII tag block at the top of every Slocum binary -> dict.'''
    raw = Path(path).read_bytes()[:nbytes].decode('latin-1', 'replace')
    out = {}
    for line in raw.splitlines():
        if ':' not in line:
            continue
        k, _, v = line.partition(':')
        k, v = k.strip(), v.strip()
        if not k or ' ' in k:
            break                            # past the tags, into binary
        out[k] = v
    return out


def cache_name(h):
    '''Cache file this binary needs, or None if it carries its own sensor
    list (sensor_list_factored: 0).'''
    crc = h.get('sensor_list_crc')
    if not crc:
        return None
    if h.get('sensor_list_factored', '1') == '0':
        return None
    return f'{crc.lower()}.cac'


def find_on_disk(name):
    hits = []
    for r in SEARCH_ROOTS:
        root = Path(r).expanduser()
        if not root.exists():
            continue
        for p in root.rglob('*'):
            if p.is_file() and p.name.lower() == name:
                hits.append(p)
    return hits


#%% ---------------- inspect both file types ----------------
inbox = config.glider_inbox()
print(f'glider : {config.GLIDER}')
print(f'inbox  : {inbox}')
print(f'cache  : {config.CACHE}  '
      f'({len(list(config.CACHE.glob("*.cac")))} *.cac)\n')

needed = {}
for ext in (config.GLIDERSUFFIX, config.SCISUFFIX):
    files = config.binaries_in(inbox, ext)
    allf = config._raw_binaries_in(inbox, ext)
    print(f'--- *.{ext} : {len(allf)} in folder, {len(files)} accepted ---')
    if not files:
        print('   nothing accepted - check the name filter / deployment_start')
        continue
    sizes = [f.stat().st_size for f in files]
    print(f'   size: min {min(sizes)} B, median '
          f'{sorted(sizes)[len(sizes)//2]} B, max {max(sizes)} B')
    if max(sizes) < 500:
        print('   !! every file is tiny - these carry no data at all')

    for f in files[:N_SHOW]:
        h = header(f)
        cac = cache_name(h)
        here = (config.CACHE / cac).exists() if cac else True
        print(f'   {f.name}: {f.stat().st_size} B, '
              f'crc {h.get("sensor_list_crc", "?")}, '
              f'factored {h.get("sensor_list_factored", "?")}, '
              f'sensors/cycle {h.get("sensors_per_cycle", "?")}')
        print(f'      needs cache {cac or "(none - self-contained)"} '
              f'-> {"PRESENT" if here else "MISSING"}')
        if cac and not here:
            needed[cac] = f

#%% ---------------- what dbdreader actually says ----------------
print('\n--- opening one file of each type with dbdreader ---')
try:
    import dbdreader
    import numpy as np
except ImportError as e:
    dbdreader = None
    print(f'   dbdreader not importable ({e}) - skipping this check')

for ext in (config.GLIDERSUFFIX, config.SCISUFFIX):
    if dbdreader is None:
        break
    files = config.binaries_in(inbox, ext)
    if not files:
        continue
    f = files[len(files) // 2]               # a middle file, not the first
    print(f'\n{f.name}')
    try:
        d = dbdreader.DBD(str(f), cacheDir=str(config.CACHE))
        names = list(d.parameterNames)
        print(f'   opened, {len(names)} parameters')
        got = 0
        for p in names[:40]:
            try:
                t, _ = d.get(p)
                got += np.size(t) > 0
            except Exception:
                pass
        print(f'   {got} of the first {min(40, len(names))} carry data')
        d.close()
    except Exception as e:
        print(f'   FAILED: {type(e).__name__}: {e}')

#%% ---------------- hunt for the missing caches ----------------
if not needed:
    print('\nevery cache these files ask for is already in place.')
else:
    print(f'\n--- hunting for {len(needed)} missing cache file(s) ---')
    for cac, src in needed.items():
        hits = find_on_disk(cac)
        print(f'{cac}  (needed by {src.name})')
        if not hits:
            print('   NOT ON THIS MACHINE. It lives on the dockserver/SFMC '
                  'or the glider itself.\n'
                  '   Nothing local can fix this - fetch it from there and '
                  f'drop it in {config.CACHE}.')
            continue
        for p in hits:
            print(f'   found: {p}')
        if COPY:
            shutil.copy2(hits[0], config.CACHE / cac)
            print(f'   -> copied into {config.CACHE}')
        else:
            print(f'   rerun with COPY=1 to copy it in, or:\n'
                  f'     cp {hits[0]} {config.CACHE}/{cac}')

print('\ndone. If the caches are all present and dbdreader still fails, the '
      'exception\nprinted above is the real cause - send me that line.')

# %%