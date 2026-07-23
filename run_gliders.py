'''
run_gliders.py
Process several gliders. One subprocess each, so config.GLIDER is fixed for
the life of the process and nothing has to be reloaded.

Output is streamed live, prefixed with the glider name, and also written to
logs/<glider>_<timestamp>.log

    python run_gliders.py
'''
#%% ---------------- settings ----------------
GLIDERS  = ['selkie', 'unit_1272']
SCRIPTS  = ['01_process_to_nc.py', '04_interactive_html.py', '05_interactive_html_merge_gliders.py']
PARALLEL = 2        # gliders at a time. 1 = sequential, and the output is
                    # then readable as one continuous log. Each glider has
                    # its own cache/ and rawnc/, so nothing is shared.
REALTIME = '1'      # '1' realtime, '0' recovered
QUIET    = False    # True = only the log files + the final summary

# ---------------- run ----------------
import os, subprocess, sys, threading, time
import datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


#check for git to work 
LOGS = Path(__file__).resolve().parent / 'logs'
LOGS.mkdir(exist_ok=True)
_print_lock = threading.Lock()
_stamp = dt.datetime.now().strftime('%Y%m%d-%H%M')


def run(glider):
    env = {**os.environ,
           'GLIDER': glider,
           'REALTIME': REALTIME,
           'PYTHONUNBUFFERED': '1'}   # without this the child buffers stdout
                                      # and nothing appears until it exits
    log = LOGS / f'{glider}_{_stamp}.log'
    t0 = time.time()

    with open(log, 'w') as fh:
        for script in SCRIPTS:
            header = f'===== {glider} : {script} ====='
            with _print_lock:
                if not QUIET:
                    print(header, flush=True)
            fh.write(header + '\n')

            p = subprocess.Popen(
                [sys.executable, '-u', script], env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1)

            for line in p.stdout:            # streams as it arrives
                fh.write(line)
                if not QUIET:
                    with _print_lock:
                        print(f'[{glider}] {line}', end='', flush=True)

            if p.wait():
                return glider, script, p.returncode, log, time.time() - t0

    return glider, None, 0, log, time.time() - t0


results = []
with ThreadPoolExecutor(max_workers=PARALLEL) as ex:
    futures = [ex.submit(run, g) for g in GLIDERS]
    for f in as_completed(futures):
        results.append(f.result())

print('\n' + '=' * 60)
for glider, script, code, log, secs in sorted(results):
    if code:
        print(f'FAIL  {glider:12s} in {script} (exit {code})  {secs:5.0f} s'
              f'  -> {log.name}')
    else:
        print(f'ok    {glider:12s} {secs:5.0f} s  -> {log.name}')
if any(r[2] for r in results):
    sys.exit(1)

# %%