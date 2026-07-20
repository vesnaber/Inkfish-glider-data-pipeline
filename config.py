'''
config.py
ONE place to set the glider and the paths. Every script imports this, so a
new user only edits this file (plus deployment.yml) after cloning.
Paths auto-detect from this file's location -> works on laptop / EC2 / Mac.
'''
#%%
from pathlib import Path
import numpy as np

# ============================================================
# EDIT THIS
# ============================================================
GLIDER = 'unit_1272'          # e.g. 'selkie', 'unit_1272'  -> used in filenames
                           # must match metadata:glider_name in deployment.yml

REALTIME = True            # True  -> realtime files: sbd (flight) / tbd (science)
                           # False -> recovered full-res: dbd (flight) / ebd (science)

# ============================================================
# paths (usually leave alone)
# ============================================================
ROOT        = Path(__file__).resolve().parent
DATA        = ROOT / 'data'              # each download is a subfolder in here
CACHE       = ROOT / 'cache'
DEPLOYMENT  = ROOT / f'deployment_{GLIDER}.yml'
SENSORLIST  = ROOT / 'sensor_list.txt'

L0_TS       = ROOT / 'L0-timeseries'
L0_PROFILES = ROOT / 'L0-profiles'
L0_GRID     = ROOT / 'L0-gridfiles'
RAWNC       = ROOT / 'rawnc'
PLOTS       = ROOT / 'plots'
HTML        = ROOT / 'interactive'

for _d in (DATA, CACHE, L0_TS, L0_PROFILES, L0_GRID, RAWNC, PLOTS):
    _d.mkdir(parents=True, exist_ok=True)

SCISUFFIX    = 'tbd' if REALTIME else 'ebd'
GLIDERSUFFIX = 'sbd' if REALTIME else 'dbd'


# ============================================================
# helpers
# ============================================================
def latest_data_dir(verbose=True):
    '''Newest subfolder of data/ that contains glider binaries.'''
    def has_binaries(d):
        return any(d.glob(f'*.{GLIDERSUFFIX}')) or any(d.glob(f'*.{GLIDERSUFFIX.upper()}'))

    cands = sorted((d for d in DATA.iterdir() if d.is_dir() and has_binaries(d)),
                   key=lambda d: d.name)
    if not cands:
        raise FileNotFoundError(
            f'no folder in {DATA} contains *.{GLIDERSUFFIX} files.\n'
            f'Put your download folder in data/ (or set REALTIME correctly).')
    d = cands[-1]
    if verbose:
        print(f'DATA FOLDER: using the newest one -> {d.name}')
        if len(cands) > 1:
            print(f'  ({len(cands)} folders available: '
                  f'{", ".join(c.name for c in cands)})')
        print('  To use a different one, set DATA_DIR manually at the top '
              'of 01_process_to_nc.py')
    return d


def newest_nc(folder, must_contain=None):
    '''Newest .nc in a folder (by modification time). must_contain filters
    on filename, e.g. the glider name.'''
    files = sorted(Path(folder).glob('*.nc'), key=lambda f: f.stat().st_mtime)
    if must_contain:
        hits = [f for f in files if must_contain in f.name]
        if hits:
            files = hits
        elif files:
            print(f'WARNING: no file in {folder} has "{must_contain}" in its '
                  f'name - is GLIDER set correctly in config.py?')
    if not files:
        raise FileNotFoundError(f'no .nc files in {folder} - run 01 first')
    if len(files) > 1:
        print(f'  {folder.name}: {len(files)} files, using the newest: '
              f'{files[-1].name}')
    else:
        print(f'  loading {files[-1].name}')
    return files[-1]


def clear_outputs(dirs=None):
    '''Delete old .nc so a rerun cannot leave stale files behind.'''
    dirs = dirs or (L0_TS, L0_PROFILES, L0_GRID)
    n = 0
    for d in dirs:
        for f in Path(d).glob('*.nc'):
            f.unlink(); n += 1
    print(f'cleared {n} old .nc files from '
          f'{", ".join(Path(d).name for d in dirs)}')


def segment_table(rebuild=False, verbose=True):
    '''Map each glider SEGMENT to its time range.

    Slocum file names look like  selkie-2026-197-3-43.tbd
                                 name -year-yearday-mission-SEGMENT
    so segment 43 = the 43rd dive-segment file of that mission. This scans
    the per-segment files in rawnc/ (written by 01) and caches the result in
    segments.csv, so the plotting scripts can say "plot legs 40-43".

    Returns a list of dicts: mission, segment, start, end, file.
    '''
    import csv
    import re
    import datetime as dt

    cache = ROOT / 'segments.csv'
    if cache.exists() and not rebuild:
        rows = []
        with open(cache) as fh:
            for r in csv.DictReader(fh):
                r['mission'] = int(r['mission']); r['segment'] = int(r['segment'])
                r['start'] = np.datetime64(r['start'])
                r['end'] = np.datetime64(r['end'])
                rows.append(r)
        if rows:
            if verbose:
                print(f'{len(rows)} segments (from {cache.name}); '
                      f'rebuild with segment_table(rebuild=True)')
            return rows

    import xarray as xr
    rows = []
    for f in sorted(RAWNC.glob('*.nc')):
        # selkie-2026-197-3-43-sbd.nc -> last two numbers are mission, segment
        nums = re.findall(r'\d+', f.stem)
        if len(nums) < 2:
            continue
        mission, segment = int(nums[-2]), int(nums[-1])
        try:
            with xr.open_dataset(f) as d:
                tname = 'time' if 'time' in d else list(d.coords)[0]
                t = d[tname].values
                if t.size == 0:
                    continue
                rows.append(dict(mission=mission, segment=segment,
                                 start=np.datetime64(t.min()),
                                 end=np.datetime64(t.max()), file=f.name))
        except Exception:
            continue

    # one row per (mission, segment): merge flight + science files
    merged = {}
    for r in rows:
        k = (r['mission'], r['segment'])
        if k in merged:
            merged[k]['start'] = min(merged[k]['start'], r['start'])
            merged[k]['end'] = max(merged[k]['end'], r['end'])
        else:
            merged[k] = r
    rows = [merged[k] for k in sorted(merged)]

    if rows:
        with open(cache, 'w', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=['mission', 'segment', 'start',
                                               'end', 'file'])
            w.writeheader()
            for r in rows:
                w.writerow({**r, 'start': str(r['start']), 'end': str(r['end'])})
        if verbose:
            print(f'{len(rows)} segments found, cached in {cache.name} '
                  f'(segments {rows[0]["segment"]}-{rows[-1]["segment"]})')
    elif verbose:
        print(f'no per-segment files in {RAWNC.name}/ - run 01 first '
              f'(segment selection will be unavailable)')
    return rows


def segment_time_range(first=None, last=None, verbose=True):
    '''Time window covering segments first..last (inclusive).
    segment_time_range(43)      -> just segment 43
    segment_time_range(40, 43)  -> segments 40 to 43
    segment_time_range(-5)      -> the last 5 segments
    Returns (start, end) as numpy datetime64, or (None, None) if unknown.'''
    rows = segment_table(verbose=False)
    if not rows:
        if verbose:
            print('no segment table - showing everything')
        return None, None
    segs = [r['segment'] for r in rows]
    if first is not None and first < 0:            # last N segments
        want = segs[first:]
    else:
        lo = segs[0] if first is None else first
        hi = lo if last is None else (segs[-1] if last is None else last)
        want = [s for s in segs if lo <= s <= hi]
    sel = [r for r in rows if r['segment'] in want]
    if not sel:
        print(f'no segments matching {first}..{last} '
              f'(available: {segs[0]}-{segs[-1]}) - showing everything')
        return None, None
    t0 = min(r['start'] for r in sel)
    t1 = max(r['end'] for r in sel)
    if verbose:
        print(f'segments {sel[0]["segment"]}-{sel[-1]["segment"]} '
              f'({len(sel)} files): {str(t0)[:16]} to {str(t1)[:16]}')
    return t0, t1


if __name__ == '__main__':
    print(f'GLIDER   : {GLIDER}')
    print(f'MODE     : {"realtime" if REALTIME else "recovered (full res)"} '
          f'({GLIDERSUFFIX}/{SCISUFFIX})')
    print(f'ROOT     : {ROOT}')
    latest_data_dir()
    segment_table()

# %%
