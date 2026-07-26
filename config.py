'''
config.py
ONE place to set the glider and the paths. Every script imports this, so a
new user only edits this file (plus deployment_<glider>.yml) after cloning.
Paths auto-detect from this file's location -> works on laptop / EC2 / Mac.

TWO DEPLOYMENTS, ONE REPO
-------------------------
The same pipeline runs in two places, and they keep their glider data in
different shapes:

  REALTIME=1   the VM.  Near-real-time stream, sbd/tbd binaries, data fed in
               by the ingestion service and living OUTSIDE the repo:
                   ~/data/rt-data/<glider>/from-glider/
                   ~/data/rt-data/<glider>/logs/

  REALTIME=0   a laptop.  Recovered full-resolution dbd/ebd, data inside the
               repo:
                   <repo>/data/<glider>-from-glider/
                   <repo>/data/<glider>-logs/

REALTIME therefore picks two things at once: which binaries to read, and
where to look for them. That is convenient but they are separate questions,
so either can be overridden without touching this file:

    GLIDER_DATA_ROOT=/home/scientist/data/archived   # where the data lives
    DATA_LAYOUT=vm|local                             # how it is named there

e.g. recovered data sitting on the VM in the archive:
    REALTIME=0 DATA_LAYOUT=vm GLIDER_DATA_ROOT=~/data/archived python 01_...

OUTPUTS ALWAYS STAY IN THE REPO, in both modes - only the INPUT location
moves. Bathymetry is reference data, not stream data, so it also always
lives in <repo>/data/.

Per glider you need two hand-made inputs in the repo root:
    deployment_<glider>.yml     (you write it)
    sensor_list_<glider>.txt    (00_build_sensor_list.py writes it)

    python config.py        # print what is configured and what has been done
'''
#%% ============================================================
#   EDIT THIS   (in practice: you almost never have to)
#   ------------------------------------------------------------
#   Two machines, one repo, and you should not have to edit this
#   file to move between them. Two INDEPENDENT things are detected:
#
#   * realtime vs recovered  <- decided by the file TYPE present
#       realtime  = sbd (flight) / tbd (science)
#       recovered = dbd (flight) / ebd (science)
#     so realtime files copied onto a laptop are still read as
#     realtime, instead of being mistaken for recovered (which then
#     looks for dbd/ebd, finds nothing, and leaves every plot empty).
#
#   * folder layout          <- decided by WHERE the files are
#       data/<glider>-from-glider  in the repo   = local
#       ~/data/rt-data/<glider>/from-glider      = vm
#
#   They need not agree: realtime files in a local folder is exactly
#   the normal case before a glider is recovered.
#
#   Precedence for each: environment variable (REALTIME / DATA_LAYOUT)
#   -> MANUAL_* pin below -> auto-detect from the data. So on a LAPTOP
#   in VS Code you just press Run - no terminal, no REALTIME= prefix,
#   nothing to accidentally commit.
#   ============================================================
import os
from pathlib import Path

# Default glider. Override per process without editing this file:
#     GLIDER=unit_1272 python 01_process_to_nc.py
# That is how run_gliders.py drives several gliders at once - one interpreter
# each, so GLIDER is fixed for the life of the process.
GLIDER = os.environ.get('GLIDER', 'selkie')
                           # must match metadata:glider_name in the yml

# Where the VM keeps the incoming stream. Used when the layout is 'vm', and
# one of the two places auto-detect looks for data.
VM_DATA_ROOT = '~/data/rt-data'

# Pin these only to force a choice; None = auto-detect (recommended).
# Environment variables (REALTIME / DATA_LAYOUT) still override either.
MANUAL_REALTIME = True      # None | False (recovered dbd/ebd) | True (realtime sbd/tbd)
MANUAL_LAYOUT = None        # None | 'local' | 'vm'

_HERE = Path(__file__).resolve().parent
_LOCAL_INBOX = _HERE / 'data' / f'{GLIDER}-from-glider'
_VM_INBOX = Path(VM_DATA_ROOT).expanduser() / GLIDER / 'from-glider'


def _exts_in(folder):
    '''Which Slocum binary extensions actually exist in `folder`.'''
    folder = Path(folder)
    found = set()
    if folder.is_dir():
        for e in ('sbd', 'tbd', 'dbd', 'ebd'):
            if (next(folder.glob(f'*.{e}'), None)
                    or next(folder.glob(f'*.{e.upper()}'), None)):
                found.add(e)
    return found


# WHERE is the data -> which layout, preferring the repo-local folder.
_local_exts = _exts_in(_LOCAL_INBOX)
_vm_exts = _exts_in(_VM_INBOX)
if _local_exts:
    _LAYOUT_AUTO = 'local'
    _AUTO_EXTS = _local_exts
    _WHERE = f'data/{GLIDER}-from-glider'
elif _vm_exts:
    _LAYOUT_AUTO = 'vm'
    _AUTO_EXTS = _vm_exts
    _WHERE = VM_DATA_ROOT
else:
    _LAYOUT_AUTO = None
    _AUTO_EXTS = set()
    _WHERE = None

# WHAT TYPE is the data -> realtime vs recovered.
if os.environ.get('REALTIME') is not None:
    REALTIME = (os.environ['REALTIME'].strip().lower()
                not in ('0', 'false', 'no', 'off', ''))
    _REALTIME_SRC = 'REALTIME env'
elif MANUAL_REALTIME is not None:
    REALTIME = bool(MANUAL_REALTIME)
    _REALTIME_SRC = 'MANUAL_REALTIME pinned in config.py'
elif _AUTO_EXTS & {'dbd', 'ebd'}:
    REALTIME = False
    _REALTIME_SRC = f'auto (recovered dbd/ebd in {_WHERE})'
elif _AUTO_EXTS & {'sbd', 'tbd'}:
    REALTIME = True
    _REALTIME_SRC = f'auto (realtime sbd/tbd in {_WHERE})'
else:
    REALTIME = False
    _REALTIME_SRC = 'auto (no data found -> recovered default)'

#%% ============================================================
#   paths
#   ============================================================
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent

# ---- input location: this is the part that differs per deployment -------
LAYOUT = os.environ.get('DATA_LAYOUT',
                        MANUAL_LAYOUT or _LAYOUT_AUTO
                        or ('vm' if REALTIME else 'local')).lower()
if LAYOUT not in ('vm', 'local'):
    raise SystemExit(f'DATA_LAYOUT must be "vm" or "local", got {LAYOUT!r}')

DATA = DATA_DIR = ROOT / 'data'      # repo data: bathymetry, and the glider
                                     # folders too when LAYOUT == 'local'

_root_env = os.environ.get('GLIDER_DATA_ROOT')
DATA_ROOT = (Path(_root_env).expanduser().resolve() if _root_env
             else (Path(VM_DATA_ROOT).expanduser() if LAYOUT == 'vm'
                   else DATA))


def glider_inbox(glider=None):
    '''The one folder this glider's binaries arrive in.
        vm    -> <DATA_ROOT>/<glider>/from-glider
        local -> <DATA_ROOT>/<glider>-from-glider
    '''
    g = glider or GLIDER
    return (DATA_ROOT / g / 'from-glider' if LAYOUT == 'vm'
            else DATA_ROOT / f'{g}-from-glider')


def glider_logs_dir(glider=None):
    '''Surface dialogs FROM the glider - raw input, so it sits next to the
    binaries. NOT the repo-root logs/, which is this pipeline's own log.
        vm    -> <DATA_ROOT>/<glider>/logs
        local -> <DATA_ROOT>/<glider>-logs
    '''
    g = glider or GLIDER
    return (DATA_ROOT / g / 'logs' if LAYOUT == 'vm'
            else DATA_ROOT / f'{g}-logs')


DATA_GLIDER = glider_inbox()         # binaries in
GLIDER_LOGS = glider_logs_dir()      # surface dialogs in

# shared reference data, always in the repo - it is not streamed
BATHY_XYZ_DIR = DATA / 'bathymetry_xyz'      # ASCII "lon lat depth" grids
BATHY_IMG_DIR = DATA / 'bathymetry_image'    # map image + a .bounds sidecar

# ---- per-glider inputs (hand-made / written by 00) ----------------------
DEPLOYMENT = ROOT / f'deployment_{GLIDER}.yml'
SENSORLIST = ROOT / f'sensor_list_{GLIDER}.txt'

# ---- per-glider outputs: always in the repo, both modes -----------------
CACHE        = ROOT / 'cache' / GLIDER       # dbdreader cache; per glider so
                                             # parallel runs cannot race
RAWNC        = ROOT / 'rawnc' / GLIDER
RAWNC_SEG    = RAWNC / 'segments'            # ARCHIVE: one .nc per binary
                                             # segment. Only 01 writes here,
                                             # and only ever adds.
RAWNC_WORK   = RAWNC / '_mergework'          # disposable copy the merge is
                                             # allowed to consume
RAWNC_MERGED = RAWNC / 'merged'
L0_TS        = ROOT / 'L0-timeseries' / GLIDER
L0_PROFILES  = ROOT / 'L0-profiles' / GLIDER
L0_GRID      = ROOT / 'L0-gridfiles' / GLIDER
L0_LOGS      = ROOT / 'L0-logs' / GLIDER     # parsed surface dialogs (03)
PLOTS        = ROOT / 'plots' / GLIDER
HTML         = ROOT / 'interactive' / GLIDER
STATE        = ROOT / '.state' / GLIDER      # stage fingerprints,
                                             # segments.csv, *_used files

for _d in (DATA, BATHY_XYZ_DIR, BATHY_IMG_DIR, CACHE, RAWNC_SEG,
           RAWNC_MERGED, L0_TS, L0_PROFILES, L0_GRID, L0_LOGS, PLOTS, HTML,
           STATE):
    _d.mkdir(parents=True, exist_ok=True)

# Input folders are only created when we own them. On the VM they belong to
# the ingestion service, and silently creating an empty ~/data/rt-data tree
# on a laptop that set REALTIME=1 by accident would hide the real problem.
if LAYOUT == 'local':
    for _d in (DATA_GLIDER, GLIDER_LOGS):
        _d.mkdir(parents=True, exist_ok=True)
elif not DATA_ROOT.exists():
    print(f'WARNING: DATA_LAYOUT=vm but {DATA_ROOT} does not exist.\n'
          f'         Set GLIDER_DATA_ROOT, or REALTIME=0 for the local '
          f'layout.')

SCISUFFIX    = 'tbd' if REALTIME else 'ebd'
GLIDERSUFFIX = 'sbd' if REALTIME else 'dbd'


def where(verbose=True):
    '''One-line summary of which deployment we think we are in.'''
    lines = [
        f'glider     : {GLIDER}',
        f'mode       : {"realtime" if REALTIME else "recovered"} '
        f'({GLIDERSUFFIX}/{SCISUFFIX})   [{_REALTIME_SRC}]',
        f'layout     : {LAYOUT}'
        + ('   (from DATA_LAYOUT)' if 'DATA_LAYOUT' in os.environ else ''),
        f'data root  : {DATA_ROOT}'
        + ('   (from GLIDER_DATA_ROOT)' if _root_env else ''),
        f'  binaries : {DATA_GLIDER}'
        + ('' if DATA_GLIDER.exists() else '   <-- MISSING'),
        f'  dialogs  : {GLIDER_LOGS}'
        + ('' if GLIDER_LOGS.exists() else '   <-- MISSING'),
        f'outputs    : {ROOT}',
        f'dep. start : {deployment_start() or "not in yml - no date filter"}'
        + ('' if FILE_FILTER else '   (GLIDER_FILE_FILTER=0: filter OFF)'),
    ]
    if verbose:
        print('\n'.join(lines))
    return lines


#%% ============================================================
#   bathymetry - optional, shared across gliders, auto-discovered
#   ------------------------------------------------------------
#   Nothing here is location-specific: drop files in the folders and they
#   are found. Everything still works without them - the 3D tab loses its
#   seabed, the map tab loses its image.
#   ============================================================
XYZ_SUFFIXES = ('.xyz', '.txt', '.asc', '.dat')
IMG_SUFFIXES = ('.png', '.jpg', '.jpeg', '.webp')
LOG_SUFFIXES = ('.log', '.txt', '.dat', '.dlg', '.nlg', '')
                        # '' matches extensionless files on purpose -
                        # dockserver surface dialogs are saved under every
                        # naming scheme there is.


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


def find_glider_logs(glider=None, verbose=True):
    '''Every surface-dialog file for this glider, oldest name first.

    No filtering on the glider name: the folder is already per glider, and
    the dialogs are usually named by date or segment rather than by vehicle.
    03 drops any record whose "Vehicle Name:" turns out to belong to someone
    else, so a stray file cannot contaminate the output.
    '''
    d = glider_logs_dir(glider)
    if not d.exists():
        if verbose:
            print(f'   no {d} - nothing to parse')
        return []
    hits = sorted(p for p in d.rglob('*')
                  if p.is_file() and not p.name.startswith('.')
                  and p.suffix.lower() in LOG_SUFFIXES)
    if verbose:
        print(f'   {len(hits)} log files in {d}')
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
#   ------------------------------------------------------------
#   Only binaries named  <glider>-YYYY-DDD-M-S.<ext>  (or with _ as the
#   separator) are accepted, and only when the mission date in the name is
#   on/after deployment_start: in the yml. Everything else - other gliders,
#   8.3 DOS names, older missions still sitting in the download folder - is
#   excluded and reported ONCE per folder. This is what stops old datasets
#   from crashing the conversion (missing caches) or polluting the merge.
#
#   Escape hatch if a dataset ever arrives with 8.3 names (straight off the
#   glider flash):  GLIDER_FILE_FILTER=0 python 01_process_to_nc.py
#   ============================================================
import re

FILE_FILTER = os.environ.get('GLIDER_FILE_FILTER', '1').lower() \
    not in ('0', 'false', 'no')

# name-YYYY-DDD-M-S ;  - and _ both accepted as separators
_BIN_RE = re.compile(r'^(?P<name>.+?)[-_](?P<year>(?:19|20)\d{2})'
                     r'[-_](?P<yday>\d{1,3})[-_]\d+[-_]\d+$', re.I)

_DEP_START = {}          # glider -> np.datetime64 or None (cached)


def deployment_start(glider=None):
    '''metadata:deployment_start from deployment_<glider>.yml as a
    np.datetime64, or None. Top-level deployment_start is accepted too -
    GUESSING!! that some ymls keep it outside metadata; both are checked so
    either spelling works.'''
    g = glider or GLIDER
    if g in _DEP_START:
        return _DEP_START[g]
    start = None
    yml = ROOT / f'deployment_{g}.yml'
    if yml.exists():
        import yaml
        try:
            dep = yaml.safe_load(yml.read_text()) or {}
            raw = ((dep.get('metadata') or {}).get('deployment_start')
                   or dep.get('deployment_start'))
            if raw:
                start = np.datetime64(
                    str(raw).strip().replace('Z', '').replace(' ', 'T')[:19])
        except Exception as e:
            print(f'   could not read deployment_start from {yml.name}: {e}')
    _DEP_START[g] = start
    return start


def binary_date(path):
    '''Mission date encoded in a Slocum long file name, or None.
    selkie-2026-197-3-43.sbd -> 2026-01-01 + 197 days.
    GUESSING!! that the yearday in Slocum names is 0-based (day 0 = Jan 1);
    accept_binary() compares with one day of slack either way, so an
    off-by-one here cannot drop real data.'''
    m = _BIN_RE.match(Path(path).stem)
    if not m:
        return None
    return (np.datetime64(f'{m["year"]}-01-01')
            + np.timedelta64(int(m['yday']), 'D'))


def accept_binary(path, glider=None):
    '''-> (keep: bool, why: str). why is "" | "name" | "old".
    Keep = long Slocum name, glider name matches, mission date on/after
    deployment_start (minus 1 day slack; the date in the name is the day the
    MISSION started, which can precede the yml start slightly).'''
    m = _BIN_RE.match(Path(path).stem)
    g = (glider or GLIDER).lower().replace('_', '-')
    if not m or m['name'].lower().replace('_', '-') != g:
        return False, 'name'
    start = deployment_start(glider)
    if start is not None:
        d = binary_date(path)
        if d is not None and d < start - np.timedelta64(1, 'D'):
            return False, 'old'
    return True, ''


_FILTER_REPORTED = set()


def _raw_binaries_in(folder, ext):
    '''All *.ext in a folder, de-duplicated across upper/lower case.
    On case-insensitive filesystems (macOS, Windows) glob('*.sbd') and
    glob('*.SBD') return the SAME files, so globbing both and concatenating
    double-counts everything.'''
    seen = {}
    for pat in (f'*.{ext}', f'*.{ext.upper()}'):
        for f in Path(folder).glob(pat):
            seen[f.resolve()] = f
    return sorted(seen.values())


def binaries_in(folder, ext, glider=None, filtered=None):
    '''Binaries in `folder` that belong to THIS glider and THIS deployment
    (see the header of this section). filtered=False returns everything.'''
    files = _raw_binaries_in(folder, ext)
    if filtered is None:
        filtered = FILE_FILTER
    if not filtered or not files:
        return files

    keep, bad_name, too_old = [], [], []
    for f in files:
        ok, why = accept_binary(f, glider)
        (keep if ok else (too_old if why == 'old' else bad_name)).append(f)

    tag = (str(Path(folder).resolve()), ext)
    if (bad_name or too_old) and tag not in _FILTER_REPORTED:
        _FILTER_REPORTED.add(tag)
        start = deployment_start(glider)
        print(f'  {Path(folder).name}: excluding '
              f'{len(bad_name) + len(too_old)}/{len(files)} *.{ext} '
              f'({len(bad_name)} not named <glider>-YYYY-DDD-M-S, '
              f'{len(too_old)} from before deployment_start '
              f'{str(start)[:10] if start is not None else "?"})')
        if not keep:
            print(f'    !! NOTHING left after filtering. If these files are '
                  f'real (e.g. 8.3 names off the\n'
                  f'    glider flash), rerun with GLIDER_FILE_FILTER=0, or '
                  f'rename them to the long form.')
    return keep


def stage_inputs(folder, glider=None, verbose=True):
    '''pyglider is handed a whole DIRECTORY and converts every binary in it,
    so filtering the file LIST is not enough - old/foreign files in the
    folder would still be read (and crash on missing caches). This links the
    accepted binaries of `folder` into .state/<glider>/staged/<name>/ and
    returns that path; the converter can then only see the right files.
    Symlinks where possible, copies where not (Windows). Any *.cac cache
    files sitting next to the binaries are copied into CACHE too - the
    realtime stream ships them alongside the data.'''
    folder = Path(folder)
    dest = STATE / 'staged' / folder.name
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    n = 0
    for ext in (GLIDERSUFFIX, SCISUFFIX):
        for f in binaries_in(folder, ext, glider):
            link = dest / f.name
            try:
                link.symlink_to(f.resolve())
            except OSError:
                shutil.copy2(f, link)
            n += 1
    n_cac = 0
    # cache files travel under several conventions: next to the binaries, in
    # a cache/ sibling, or one level up. Copy any we can find - a missing
    # SCIENCE cache is exactly what makes every .tbd fail to convert while
    # the .sbd sail through.
    cand_dirs = [folder, folder / 'cache', folder.parent,
                 folder.parent / 'cache', DATA_ROOT / 'cache']
    for cd in cand_dirs:
        if not cd.is_dir():
            continue
        for pat in ('*.cac', '*.CAC'):
            for c in cd.glob(pat):
                tgt = CACHE / c.name.lower()
                if not tgt.exists():
                    shutil.copy2(c, tgt)
                    n_cac += 1
    if verbose:
        print(f'      staged {n} accepted binaries'
              + (f' + {n_cac} new cache files' if n_cac else ''))
    return dest


def _matches_glider(path, glider=None):
    '''True if a file or folder name contains the glider name (case
    insensitive).'''
    return (glider or GLIDER).lower() in path.name.lower()


def legacy_data_dirs(glider=None, verbose=True):
    '''Old timestamped download folders that still hold binaries.

    Local layout only - on the VM the ingestion service owns the tree and
    there is exactly one from-glider folder per glider. They are still
    processed so nothing is lost mid-migration, but reported with the exact
    mv command, because one growing inbox is the whole point.
    '''
    if LAYOUT != 'local':
        return []
    glider = glider or GLIDER
    inbox = glider_inbox(glider)
    hits = sorted(d for d in DATA_ROOT.iterdir()
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
    newest data use the last entry, and the inbox is where new files arrive.
    Conversion is incremental against rawnc/<glider>/segments/, so
    re-listing the whole inbox every run costs nothing.
    '''
    glider = glider or GLIDER
    inbox = glider_inbox(glider)
    if LAYOUT == 'local':
        inbox.mkdir(parents=True, exist_ok=True)

    dirs = legacy_data_dirs(glider, verbose=verbose)
    n_inbox = len(binaries_in(inbox, GLIDERSUFFIX)) if inbox.exists() else 0
    if n_inbox:
        dirs = dirs + [inbox]

    if not dirs:
        msg = (f'no *.{GLIDERSUFFIX} files for "{glider}".\n'
               f'Looked in : {inbox}\n'
               f'layout    : {LAYOUT}   data root: {DATA_ROOT}\n'
               + ('That folder does not exist. Wrong machine? The VM layout '
                  'is REALTIME=1, the laptop layout REALTIME=0.\n'
                  if not inbox.exists() else '')
               + 'Override with GLIDER_DATA_ROOT / DATA_LAYOUT if needed.')
        if strict:
            raise FileNotFoundError(msg)
        print(f'WARNING: {msg}')
        return []

    if verbose:
        n = sum(len(binaries_in(d, GLIDERSUFFIX)) for d in dirs)
        done = len(list(RAWNC_SEG.glob('*.nc')))
        print(f'DATA [{glider}]: {n} *.{GLIDERSUFFIX} across {len(dirs)} '
              f'folder(s); {done} segments already converted')
        print(f'  inbox [{LAYOUT}]: {inbox}  ({n_inbox} files)'
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
    where()
    print(f'yml        : {DEPLOYMENT.name}'
          f'{"" if DEPLOYMENT.exists() else "   <-- MISSING"}')
    print(f'sensors    : {SENSORLIST.name}'
          f'{"" if SENSORLIST.exists() else "   <-- MISSING, run 00"}')

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
    print(f'\nsurface dialogs: {len(_logs)} files in {GLIDER_LOGS}'
          f'{"   <-- empty, Logs/Battery tabs will be skipped" if not _logs else ""}')

    print()
    all_data_dirs(strict=False)
    segment_table()
    status()

# %%