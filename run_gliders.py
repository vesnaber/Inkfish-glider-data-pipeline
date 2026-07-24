'''
run_gliders.py
Process several gliders. One subprocess each, so config.GLIDER is fixed for
the life of the process and nothing has to be reloaded.

Output is streamed live, prefixed with the glider name, and also written to
logs/<glider>_<timestamp>.log

    python run_gliders.py                        # every configured glider
    python run_gliders.py -g selkie              # just one
    python run_gliders.py -g selkie unit_1272    # or several
    python run_gliders.py --realtime 0           # laptop: recovered, local data
    python run_gliders.py --only 04 05           # rerun just the html
    python run_gliders.py --skip 01              # everything but the slow one
    python run_gliders.py --list                 # what would run, then stop

REALTIME picks the deployment: 1 = the VM (realtime sbd/tbd, data under
~/data/rt-data/), 0 = a laptop (recovered dbd/ebd, data under <repo>/data/).
--data-root and --layout override that split when the two do not coincide.
'''
#%% ---------------- settings ----------------
SCRIPTS = ['00_build_sensor_list.py',
           '01_process_to_nc.py',
           '03_process_glider_logs.py',
           '03b_battery_status.py',
           '04_interactive_html.py',
           '05_interactive_html_merge_gliders.py']

DEFAULT_PARALLEL = 2   # gliders at a time. 1 = sequential, and the output is
                       # then readable as one continuous log. Each glider has
                       # its own cache/ and rawnc/, so nothing is shared.
DEFAULT_REALTIME = True

# ---------------- run ----------------
import argparse
import datetime as dt
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def known_gliders():
    '''Every glider with a deployment yml - that file is the only thing
    that makes a glider "configured" as far as the pipeline cares.'''
    return sorted(p.stem.replace('deployment_', '')
                  for p in ROOT.glob('deployment_*.yml'))


def as_bool(v):
    '''argparse hands back whatever the shell gave us, so accept the lot.
    NOTE the child gets '1'/'0' as a STRING - subprocess env values must be
    strings, and passing a bool raises TypeError deep inside Popen.'''
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ('1', 'true', 'yes', 'y', 'on', 'realtime', 'rt'):
        return True
    if s in ('0', 'false', 'no', 'n', 'off', 'recovered'):
        return False
    raise argparse.ArgumentTypeError(
        f'expected a yes/no value, got {v!r} '
        f'(use 1/0, true/false, realtime/recovered)')


def pick_scripts(only, skip):
    '''--only / --skip match on any part of the filename, so "04",
    "04_interactive_html.py" and "interactive" all work.'''
    chosen = SCRIPTS
    if only:
        chosen = [s for s in SCRIPTS if any(o in s for o in only)]
        unmatched = [o for o in only if not any(o in s for s in SCRIPTS)]
        if unmatched:
            raise SystemExit(
                f'--only matched nothing for: {", ".join(unmatched)}\n'
                f'available: {", ".join(SCRIPTS)}')
    if skip:
        chosen = [s for s in chosen if not any(k in s for k in skip)]
    if not chosen:
        raise SystemExit('nothing left to run after --only/--skip')
    return chosen


p = argparse.ArgumentParser(
    description='Run the pipeline for one or more gliders.',
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog=__doc__)
p.add_argument('-g', '--gliders', nargs='+', metavar='NAME',
               help='glider names, space or comma separated. '
                    'Default: every deployment_<glider>.yml in the repo.')
p.add_argument('-r', '--realtime', type=as_bool, default=DEFAULT_REALTIME,
               metavar='0|1',
               help='1 = VM, realtime sbd/tbd (default). '
                    '0 = laptop, recovered dbd/ebd.')
p.add_argument('--data-root', metavar='PATH',
               help='override where the glider data lives '
                    '(sets GLIDER_DATA_ROOT)')
p.add_argument('--layout', choices=['vm', 'local'],
               help='override how the data folders are named '
                    '(sets DATA_LAYOUT)')
p.add_argument('-j', '--parallel', type=int, default=DEFAULT_PARALLEL,
               metavar='N',
               help=f'gliders at a time (default {DEFAULT_PARALLEL}; '
                    f'1 = readable continuous output)')
p.add_argument('--only', nargs='+', metavar='MATCH',
               help='run only the scripts whose name contains one of these')
p.add_argument('--skip', nargs='+', metavar='MATCH',
               help='skip the scripts whose name contains one of these')
p.add_argument('-q', '--quiet', action='store_true',
               help='only the log files and the final summary')
p.add_argument('--list', action='store_true',
               help='print what would run, then stop')
args = p.parse_args()

# "-g selkie,unit_1272" and "-g selkie unit_1272" both work.
# Without the split, a bare string would be iterated CHARACTER BY CHARACTER
# and you would get one thread per letter.
GLIDERS = args.gliders or known_gliders()
GLIDERS = [g.strip() for item in GLIDERS for g in item.split(',') if g.strip()]

if not GLIDERS:
    raise SystemExit(f'no gliders. Either pass -g <name>, or add a '
                     f'deployment_<glider>.yml to {ROOT}')

unknown = [g for g in GLIDERS if g not in known_gliders()]
if unknown:
    raise SystemExit(f'no deployment yml for: {", ".join(unknown)}\n'
                     f'configured: {", ".join(known_gliders()) or "(none)"}')

SCRIPTS_TO_RUN = pick_scripts(args.only, args.skip)
missing = [s for s in SCRIPTS_TO_RUN if not (ROOT / s).exists()]
if missing:
    raise SystemExit(f'script(s) not found in {ROOT}: {", ".join(missing)}')

REALTIME = '1' if args.realtime else '0'      # env values must be strings
PARALLEL = max(1, args.parallel)
QUIET = args.quiet

EXTRA_ENV = {}
if args.data_root:
    EXTRA_ENV['GLIDER_DATA_ROOT'] = str(Path(args.data_root).expanduser())
if args.layout:
    EXTRA_ENV['DATA_LAYOUT'] = args.layout

print(f'gliders  : {", ".join(GLIDERS)}')
print(f'mode     : {"realtime / VM (sbd,tbd)" if args.realtime else "recovered / local (dbd,ebd)"}')
for k, v in EXTRA_ENV.items():
    print(f'override : {k}={v}')
print(f'parallel : {PARALLEL}')
print(f'scripts  : {", ".join(SCRIPTS_TO_RUN)}')
if args.list:
    raise SystemExit(0)

LOGS = ROOT / 'logs'
LOGS.mkdir(exist_ok=True)
_print_lock = threading.Lock()
_stamp = dt.datetime.now().strftime('%Y%m%d-%H%M')


def run(glider):
    env = {**os.environ, **EXTRA_ENV,
           'GLIDER': glider,
           'REALTIME': REALTIME,
           'PYTHONUNBUFFERED': '1'}   # without this the child buffers stdout
                                      # and nothing appears until it exits
    log = LOGS / f'{glider}_{_stamp}.log'
    t0 = time.time()

    with open(log, 'w') as fh:
        for script in SCRIPTS_TO_RUN:
            header = f'===== {glider} : {script} ====='
            with _print_lock:
                if not QUIET:
                    print(header, flush=True)
            fh.write(header + '\n')

            proc = subprocess.Popen(
                [sys.executable, '-u', script], env=env, cwd=ROOT,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1)

            for line in proc.stdout:          # streams as it arrives
                fh.write(line)
                if not QUIET:
                    with _print_lock:
                        print(f'[{glider}] {line}', end='', flush=True)

            if proc.wait():
                return glider, script, proc.returncode, log, time.time() - t0

    return glider, None, 0, log, time.time() - t0


results = []
with ThreadPoolExecutor(max_workers=PARALLEL) as ex:
    futures = [ex.submit(run, g) for g in GLIDERS]
    for f in as_completed(futures):
        results.append(f.result())

print('\n' + '=' * 60)
for glider, script, code, log, secs in sorted(results, key=lambda r: r[0]):
    if code:
        print(f'FAIL  {glider:12s} in {script} (exit {code})  {secs:5.0f} s'
              f'  -> {log.name}')
    else:
        print(f'ok    {glider:12s} {secs:5.0f} s  -> {log.name}')
if any(r[2] for r in results):
    sys.exit(1)

# %%