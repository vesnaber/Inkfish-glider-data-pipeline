'''
config.py
ONE place to set the glider and the paths. Every script imports this, so a
new user only edits this file (plus deployment_<glider>.yml) after cloning.
Paths auto-detect from this file's location -> works on laptop / EC2 / Mac.

Per glider you need two hand-made inputs in the repo root:
    deployment_<glider>.yml     (you write it)
    sensor_list_<glider>.txt    (00_build_sensor_list.py writes it)

Outputs go in one subfolder per glider, so several gliders can be processed
side by side without overwriting each other.

    python config.py        # print what is configured and what has been done
'''
#%% ============================================================
#   EDIT THIS
#   ============================================================
import os

# Default glider. Override per process without editing this file:
#     GLIDER=unit_1272 python 01_process_to_nc.py
# That is how run_gliders.py drives several gliders at once - one interpreter
# each, so GLIDER is fixed for the life of the process.
GLIDER = os.environ.get('GLIDER', 'selkie')
                           # must match metadata:glider_name in the yml

# True  -> realtime files:     sbd (flight) / tbd (science)
# False -> recovered full-res: dbd (flight) / ebd (science)
# Override with  REALTIME=0 python ...
REALTIME = os.environ.get('REALTIME', '1').lower() not in ('0', 'false', 'no')


#%% ============================================================
#   paths (usually leave alone)
#   ------------------------------------------------------------
#   MIGRATION from the old layout:
#     - outputs live one level deeper, in <folder>/<glider>/
#     - sensor_list.txt is now sensor_list_<glider>.txt
#     - rawnc/<glider>/ is split into segments/ and merged/
#     - bathymetry moved into data/bathymetry_xyz/ and data/bathymetry_image/
#   Easiest migration: config.clear_outputs(rawnc=True) once per glider,
#   then rerun 01. It reconverts, but from then on it is incremental.
#   ============================================================
from pathlib import Path
import numpy as np

ROOT        = Path(__file__).resolve().parent

# shared across gliders
DATA          = DATA_DIR = ROOT / 'data'     # one subfolder per download
BATHY_XYZ_DIR = DATA / 'bathymetry_xyz'      # ASCII "lon lat depth" grids,
                                             # for the 3D terrain
BATHY_IMG_DIR = DATA / 'bathymetry_image'    # georeferenced image for the map
                                             # tab, plus a .bounds sidecar
DATA_GLIDER   = DATA / f'{GLIDER}-from-glider'
                                             # THE inbox. One folder per
                                             # glider, no timestamp: new
                                             # downloads just land here and
                                             # the pipeline converts whatever
                                             # is not already in
                                             # rawnc/<glider>/segments/.
GLIDER_LOGS   = DATA / f'{GLIDER}-logs'      # surface dialogs FROM the
                                             # glider. Raw input, so it sits
                                             # in data/ next to the binaries.
                                             # NOT the repo-root logs/, which
                                             # is this pipeline's own log.

# per-glider inputs (hand-made / written by 00)
DEPLOYMENT  = ROOT / f'deployment_{GLIDER}.yml'
SENSORLIST  = ROOT / f'sensor_list_{GLIDER}.txt'

# per-glider outputs
CACHE       = ROOT / 'cache' / GLIDER        # dbdreader cache; per glider so
                                             # parallel runs cannot race
RAWNC       = ROOT / 'rawnc' / GLIDER        # parent of the two below
RAWNC_SEG   = RAWNC / 'segments'             # ARCHIVE: one .nc per binary
                                             # segment. Only 01 writes here,
                                             # and only ever adds.
RAWNC_WORK  = RAWNC / '_mergework'           # disposable copy the merge is
                                             # allowed to consume
RAWNC_MERGED = RAWNC / 'merged'              # merged flight + science
L0_TS       = ROOT / 'L0-timeseries' / GLIDER
L0_PROFILES = ROOT / 'L0-profiles' / GLIDER
L0_GRID     = ROOT / 'L0-gridfiles' / GLIDER
L0_LOGS     = ROOT / 'L0-logs' / GLIDER      # parsed surface dialogs (03)
PLOTS       = ROOT / 'plots' / GLIDER
HTML        = ROOT / 'interactive' / GLIDER
STATE       = ROOT / '.state' / GLIDER       # stage fingerprints,
                                             # segments.csv, and the derived
                                             # *_used files
for _d in (DATA, BATHY_XYZ_DIR, BATHY_IMG_DIR, DATA_GLIDER, GLIDER_LOGS,
           CACHE, RAWNC_SEG, RAWNC_MERGED, L0_TS, L0_PROFILES, L0_GRID,
           L0_LOGS, PLOTS, HTML, STATE):
    _d.mkdir(parents=True, exist_ok=True)

SCISUFFIX    = 'tbd' if REALTIME else 'ebd'
GLIDERSUFFIX = 'sbd' if REALTIME else 'dbd'


#%% ============================================================
#   bathymetry - optional, shared across gliders, auto-discovered
#   ------------------------------------------------------------
#   Nothing here is location-specific: drop files in the folders and they
#   are found. Everything still works without them - the 3D tab loses its
#   seabed, the map tab loses its image.
#   ============================================================
XYZ_SUFFIXES = ('.xyz', '.txt', '.asc', '.dat')
IMG_SUFFIXES = ('.png', '.jpg', '.jpeg', '.webp')


def find_bathy_xyz(verbose=True):
    '''First ASCII bathymetry grid in data/bathymetry_xyz/, or None.

    The file is "lon lat depth" per line, whitespace separated, depth
    negative downward. Any name works. If you keep several, the
    alphabetically first is used - pass a path explicitly to override.'''
    hits = sorted(p for p in BATHY_XYZ_DIR.iterdir()
                  if p.is_file() and p.suffix.lower() in XYZ_SUFFIXES)
    if not hits:
        if verbose:
            print(f'   no bathymetry grid in {BATHY_XYZ_DIR.name}/ '
                  f'- 3D without terrain')
        return None
    if verbose and len(hits) > 1:
        print(f'   {len(hits)} grids in {BATHY_XYZ_DIR.name}/, '
              f'using {hits[0].name}')
    return hits[0]

LOG_SUFFIXES = ('.log', '.txt', '.dat', '.dlg', '')
                        # '' matches extensionless files on purpose -
                        # dockserver surface dialogs are saved under every
                        # naming scheme there is.
 
 
def find_glider_logs(glider=None, verbose=True):
    '''Every surface-dialog file in data/<glider>-logs/, oldest name first.
 
    No filtering on the glider name: the folder is already per glider, and
    the dialogs are usually named by date or segment rather than by vehicle.
    03_parse_logs.py drops any record whose "Vehicle Name:" turns out to
    belong to someone else, so a stray file cannot contaminate the output.
    '''
    d = DATA / f'{glider or GLIDER}-logs'
    if not d.exists():
        if verbose:
            print(f'   no {d.name}/ - nothing to parse')
        return []
    hits = sorted(p for p in d.rglob('*')
                  if p.is_file() and not p.name.startswith('.')
                  and p.suffix.lower() in LOG_SUFFIXES)
    if verbose:
        print(f'   {len(hits)} log files in {d.relative_to(ROOT)}/')
    return hits

def read_bounds(path):
    '''Geographic bounds for a map image, from a sidecar next to it.

    Accepted, in order:
        <image>.bounds.json   {"south":.., "west":.., "north":.., "east":..}
        <image>.bounds        south west north east   (one line, any spacing)
        <image>.bounds.txt    same

    Returns (south, west, north, east) or None. World files (.pgw) are NOT
    read - GUESSING!! that nobody here has one; say so and it can be added.'''
    import json
    stem = path.with_suffix('')
    for cand in (Path(f'{stem}.bounds.json'), Path(f'{stem}.bounds'),
                 Path(f'{stem}.bounds.txt')):
        if not cand.exists():
            continue
        txt = cand.read_text().strip()
        try:
            if cand.suffix == '.json' or txt.startswith('{'):
                d = json.loads(txt)
                return (float(d['south']), float(d['west']),
                        float(d['north']), float(d['east']))
            nums = [float(x) for x in txt.replace(',', ' ').split()]
            if len(nums) >= 4:
                return tuple(nums[:4])
            print(f'   {cand.name}: need 4 numbers, found {len(nums)}')
        except Exception as e:
            print(f'   could not read {cand.name}: {e}')
    return None


def bathy_image(verbose=True):
    '''(path, (south, west, north, east)) for the map tab, or (None, None).

    Looks for one image in data/bathymetry_image/ plus a bounds sidecar with
    the same stem. Without the sidecar the image cannot be placed on the map,
    so it is skipped with a clear message rather than drawn in the wrong
    spot.'''
    hits = sorted(p for p in BATHY_IMG_DIR.iterdir()
                  if p.is_file() and p.suffix.lower() in IMG_SUFFIXES)
    if not hits:
        if verbose:
            print(f'   no image in {BATHY_IMG_DIR.name}/ '
                  f'- map without bathymetry')
        return None, None
    img = hits[0]
    if verbose and len(hits) > 1:
        print(f'   {len(hits)} images in {BATHY_IMG_DIR.name}/, '
              f'using {img.name}')

    bounds = read_bounds(img)
    if bounds is None:
        print(f'   {img.name} has no bounds sidecar - skipping it.\n'
              f'   Create {img.stem}.bounds next to it, one line:\n'
              f'       south west north east\n'
              f'   e.g.  11.911967 -69.244978 12.451538 -68.610832')
        return None, None
    return img, bounds


#%% ============================================================
#   finding the right files for THIS glider
#   ============================================================
def binaries_in(folder, ext):
    '''All *.ext in a folder, de-duplicated across upper/lower case.
    On case-insensitive filesystems (macOS, Windows) glob('*.sbd') and
    glob('*.SBD') return the SAME files, so globbing both and concatenating
    double-counts everything.'''
    seen = {}
    for pat in (f'*.{ext}', f'*.{ext.upper()}'):
        for f in Path(folder).glob(pat):
            seen[f.resolve()] = f
    return sorted(seen.values())


def _matches_glider(path, glider=None):
    '''True if a file or folder name contains the glider name (case
    insensitive). Slocum binaries are normally
    <glider>-<year>-<yday>-<mission>-<segment>.sbd and download folders
    usually carry the glider name too.
    GUESSING!! - if your folders are named by date or mission only, nothing
    will match; see the note at the bottom of this file.'''
    return (glider or GLIDER).lower() in path.name.lower()


def glider_inbox(glider=None):
    '''data/<glider>-from-glider - the one folder binaries go in.'''
    return DATA / f'{glider or GLIDER}-from-glider'


def legacy_data_dirs(glider=None, verbose=True):
    '''Old timestamped download folders that still hold binaries.

    They are still processed, so nothing is lost while you migrate - but
    they are reported with the exact mv command, because one growing inbox
    is the whole point and half-migrated data is easy to forget about.
    '''
    glider = glider or GLIDER
    inbox = glider_inbox(glider)
    hits = sorted(d for d in DATA.iterdir()
                  if d.is_dir() and d.resolve() != inbox.resolve()
                  and not d.name.lower().endswith('-logs')
                  and _matches_glider(d, glider)
                  and binaries_in(d, GLIDERSUFFIX))
    if hits and verbose:
        n = sum(len(binaries_in(d, GLIDERSUFFIX)) for d in hits)
        print(f'  {len(hits)} legacy folder(s) with {n} *.{GLIDERSUFFIX} '
              f'still outside the inbox - consolidate with:')
        for d in hits:
            print(f'    mv {d}/* {inbox}/ && rmdir {d}')
    return hits


def all_data_dirs(glider=None, verbose=True, strict=True):
    '''Folders holding binaries for `glider`, INBOX LAST.

    Ordering matters: callers that want a representative sample of the
    newest data use the last entry, and the inbox is where new downloads
    arrive. Conversion is incremental against rawnc/<glider>/segments/, so
    re-listing the whole inbox every run costs nothing.
    '''
    glider = glider or GLIDER
    inbox = glider_inbox(glider)
    inbox.mkdir(parents=True, exist_ok=True)

    dirs = legacy_data_dirs(glider, verbose=verbose)
    n_inbox = len(binaries_in(inbox, GLIDERSUFFIX))
    if n_inbox:
        dirs = dirs + [inbox]

    if not dirs:
        msg = (f'no *.{GLIDERSUFFIX} files for "{glider}".\n'
               f'Put them in:  {inbox}\n'
               f'(one folder, no timestamp - new downloads just add to it)')
        if strict:
            raise FileNotFoundError(msg)
        print(f'WARNING: {msg}')
        return []

    if verbose:
        n = sum(len(binaries_in(d, GLIDERSUFFIX)) for d in dirs)
        done = len(list(RAWNC_SEG.glob('*.nc')))
        print(f'DATA [{glider}]: {n} *.{GLIDERSUFFIX} across {len(dirs)} '
              f'folder(s); {done} segments already converted')
        print(f'  inbox: {inbox.name}  ({n_inbox} files)'
              + ('   <-- EMPTY' if not n_inbox else ''))
    return dirs


def latest_data_dir(glider=None, verbose=True, strict=True):
    '''The inbox when it has data, otherwise the newest legacy folder.
    00_build_sensor_list.py uses this - it only needs a sample.'''
    d = all_data_dirs(glider, verbose=verbose, strict=strict)
    return d[-1] if d else None

def newest_nc(folder, must_contain=None, strict=True):
    '''Newest .nc in `folder` belonging to `must_contain` (defaults to
    GLIDER). strict=True raises if nothing matches, rather than handing back
    another glider's file.'''
    must_contain = GLIDER if must_contain is None else must_contain
    folder = Path(folder)
    files = sorted(folder.glob('*.nc'), key=lambda f: f.stat().st_mtime)
    if not files:
        raise FileNotFoundError(f'no .nc files in {folder} - run 01 first')

    if must_contain:
        hits = [f for f in files if must_contain.lower() in f.name.lower()]
        if not hits:
            msg = (f'no .nc in {folder} has "{must_contain}" in its name.\n'
                   f'Present: {", ".join(f.name for f in files)}\n'
                   f'Check GLIDER.')
            if strict:
                raise FileNotFoundError(msg)
            print(f'WARNING: {msg}\n  falling back to the newest file')
        else:
            files = hits

    if len(files) > 1:
        print(f'  {folder.name} [{must_contain}]: {len(files)} files, using '
              f'the newest: {files[-1].name}')
    else:
        print(f'  loading {files[-1].name}')
    return files[-1]


#%% ============================================================
#   stage state - what has already been processed
#   ------------------------------------------------------------
#   Each pipeline stage stores a fingerprint of the settings that produced
#   its output, plus the fingerprint of the stage before it. A stage reruns
#   when its own settings changed, when an upstream stage changed, or when
#   its outputs are missing. Otherwise 01 skips it.
#   ============================================================
import hashlib
import json
import shutil
import datetime as _dt

STAGES = ['rawnc', 'merge', 'timeseries', 'profiles', 'grid']


def _sha(obj):
    '''short stable hash of anything json-able'''
    return hashlib.sha1(json.dumps(obj, sort_keys=True,
                                   default=str).encode()).hexdigest()[:12]


def stage_key(name, settings, upstream=None):
    '''Fingerprint for one stage. `settings` = everything that changes this
    stage's output; `upstream` = the previous stage's key, so a change early
    in the pipeline cascades forward.'''
    return _sha({'stage': name, 'settings': settings, 'upstream': upstream})


def read_state(name):
    try:
        return json.loads((STATE / f'{name}.json').read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write_state(name, key, **extra):
    (STATE / f'{name}.json').write_text(json.dumps(
        {'key': key, 'glider': GLIDER,
         'when': _dt.datetime.now().isoformat(timespec='seconds'), **extra},
        indent=2, default=str))


def needs_rerun(name, key, outputs=(), force=False):
    '''-> (rerun: bool, why: str). `outputs` are paths that must exist for
    the stage to count as done.'''
    if force:
        return True, 'forced'
    old = read_state(name)
    if not old:
        return True, 'never run'
    if old.get('key') != key:
        return True, 'settings or upstream changed'
    missing = [p for p in outputs if p and not Path(p).exists()]
    if missing:
        return True, f'output missing ({Path(missing[0]).name})'
    return False, 'up to date'


def dir_signature(folder, pattern='*.nc'):
    '''Fingerprint of a folder's contents: file names + sizes, NOT mtimes.
    pyglider rewrites files even when nothing changed, so an mtime-based
    signature makes every downstream stage rerun on every run.'''
    files = sorted(Path(folder).glob(pattern))
    return {'n': len(files),
            'bytes': sum(f.stat().st_size for f in files),
            'hash': _sha([(f.name, f.stat().st_size) for f in files])}


def clear_stage(*names):
    '''Forget that these stages ran, so the next run redoes them.
    Deletes no data - the stage itself decides what to wipe.'''
    for n in (names or STAGES):
        (STATE / f'{n}.json').unlink(missing_ok=True)


def clear_outputs(rawnc=False, verbose=True):
    '''Delete this glider's derived .nc so a rerun cannot leave stale files
    behind. rawnc=False keeps the expensive binary conversion.'''
    dirs = [L0_TS, L0_PROFILES, L0_GRID]
    n = 0
    for d in dirs:
        for f in Path(d).glob('*.nc'):
            f.unlink()
            n += 1
    clear_stage('timeseries', 'profiles', 'grid')
    if rawnc:
        shutil.rmtree(RAWNC, ignore_errors=True)
        RAWNC_SEG.mkdir(parents=True, exist_ok=True)
        RAWNC_MERGED.mkdir(parents=True, exist_ok=True)
        clear_stage('rawnc', 'merge')
        (STATE / 'segments.csv').unlink(missing_ok=True)
    if verbose:
        print(f'[{GLIDER}] cleared {n} .nc from '
              f'{", ".join(d.parent.name for d in dirs)}'
              f'{" + rawnc (segments AND merged)" if rawnc else ""}')


def status():
    '''print what has been done for this glider'''
    print(f'\nstate [{GLIDER}]:')
    for n in STAGES:
        s = read_state(n)
        print(f'  {n:12s} {s.get("when", "-"):20s} {s.get("key", "never run")}')
    print(f'  segments on disk: {len(list(RAWNC_SEG.glob("*.nc")))}')


#%% ============================================================
#   segments (for "plot legs 40-43")
#   ============================================================
def segment_table(rebuild=False, verbose=True):
    '''Map each glider SEGMENT to its time range.

    Slocum file names look like  selkie-2026-197-3-43.tbd
                                 name -year-yearday-mission-SEGMENT
    so segment 43 = the 43rd dive-segment file of that mission. Scans the
    per-segment archive in rawnc/<glider>/segments/ (written by 01) and
    caches the result in .state/<glider>/segments.csv.

    Returns a list of dicts: mission, segment, start, end, file.
    '''
    import csv
    import re

    cache = STATE / 'segments.csv'
    if cache.exists() and not rebuild:
        rows = []
        with open(cache) as fh:
            for r in csv.DictReader(fh):
                r['mission'] = int(r['mission'])
                r['segment'] = int(r['segment'])
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
    for f in sorted(RAWNC_SEG.glob('*.nc')):
        # 01780011.sbd.nc -> the digits encode mission and segment
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

    # one row per (mission, segment): merge the flight + science files
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
                w.writerow({**r, 'start': str(r['start']),
                            'end': str(r['end'])})
        if verbose:
            print(f'{len(rows)} segments found, cached in {cache.name} '
                  f'(segments {rows[0]["segment"]}-{rows[-1]["segment"]})')
    elif verbose:
        print(f'no per-segment files in {RAWNC_SEG} - run 01 first '
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
    if first is not None and first < 0:                 # last N segments
        want = segs[first:]
    else:
        lo = segs[0] if first is None else first
        hi = lo if last is None else last
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


#%% ============================================================
#   run this file directly to check the setup
#   ============================================================
if __name__ == '__main__':
    print(f'GLIDER   : {GLIDER}')
    print(f'MODE     : {"realtime" if REALTIME else "recovered (full res)"} '
          f'({GLIDERSUFFIX}/{SCISUFFIX})')
    print(f'ROOT     : {ROOT}')
    print(f'yml      : {DEPLOYMENT.name}'
          f'{"" if DEPLOYMENT.exists() else "   <-- MISSING"}')
    print(f'sensors  : {SENSORLIST.name}'
          f'{"" if SENSORLIST.exists() else "   <-- MISSING, run 00"}')

    _legacy = ROOT / 'sensor_list.txt'
    if _legacy.exists() and not SENSORLIST.exists():
        print(f'           (found the old shared {_legacy.name} - rename it '
              f'to {SENSORLIST.name}, or just rerun 00)')

    _known = sorted(p.stem.replace('deployment_', '')
                    for p in ROOT.glob('deployment_*.yml'))
    if len(_known) > 1:
        print(f'\ngliders configured here: {", ".join(_known)}')
        print(f'  run another one with:  '
              f'GLIDER={_known[0]} python 01_process_to_nc.py')

    print('\nbathymetry (optional):')
    _x = find_bathy_xyz()
    print(f'  3D terrain : {_x.name if _x else "none"}')
    _i, _b = bathy_image()
    print(f'  map image  : {_i.name if _i else "none"}'
          f'{f"  bounds {_b}" if _b else ""}')

    _logs = find_glider_logs(verbose=False)
    print(f'\\nsurface dialogs: {len(_logs)} files in '
          f'{GLIDER_LOGS.relative_to(ROOT)}/'
          f'{"   <-- empty, Logs tab will be skipped" if not _logs else ""}')

    all_data_dirs()
    segment_table()
    status()


# ============================================================
# NOTE - if your download folders are NOT named after the glider
# ------------------------------------------------------------
# _matches_glider() only reads names. If a folder is "2026-07-18_download"
# holding binaries called "01870000.sbd", nothing matches and strict mode
# raises. Then either:
#   - rename the folders to include the glider name (simplest), or
#   - keep one data/<glider>/ subfolder per glider and set
#     DATA = ROOT / 'data' / GLIDER, or
#   - read the glider name from the binary header instead of the filename
#     (dbdreader, or the ascii header field the8x3_filename).
# ============================================================

# %%