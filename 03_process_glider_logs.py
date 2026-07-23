'''
03_parse_logs.py
Parse the Slocum surface-dialog logs into three tidy tables and write them
as parquet next to the other L0 products.

Every time the glider surfaces it dumps a status block to the console. One
log file usually holds several of those. This script cuts the text into
records (one per "Vehicle Name:" dump) and pulls out:

  surfacings  one row per status dump - time, mission/segment, the "Because:"
              reason, DR and GPS position (TooFar/Invalid are skipped),
              waypoint, abort history, device error/warning/oddity counters,
              file transfers, disk and heap, and what happened afterwards
              (resumed / aborted / went to GliderDos).
  sensors     long format: one row per (time, sensor) with value, units and
              how stale the reading was.
  devices     long format: one row per (time, device) with the cumulative
              total/mission/segment counters AND the per-record DELTA, which
              is what tells you a device just misbehaved.

    python 03_parse_logs.py
'''
#%% ============================================================
#   SETTINGS
#   ============================================================
import config

GLIDERS = [config.GLIDER]      # which gliders to parse

LOG_DIR = config.GLIDER_LOGS       # data/<glider>-logs/  - drop the surface
                                   # dialogs in there exactly as they come
                                   # off the dockserver. (The repo-root
                                   # logs/ folder is the PIPELINE's own log,
                                   # a different thing entirely.)
OUT_DIR = config.L0_LOGS           # L0-logs/<glider>/ - parquet written here

WRITE_PARQUET = True           # needs pyarrow (or fastparquet)
WRITE_CSV = True               # small human-readable copy of `surfacings`
                               # only - the sensor table is far too long

DROP_STALE_SENSORS = True      # a sensor reported "1e+308 secs ago" has never
                               # been set this mission; keep the row but mark
                               # age as NaN. True also drops it from the
                               # timeseries used by the plots.

MIN_RECORDS = 1                # warn if a file yields fewer than this


#%% ============================================================
#   setup
#   ============================================================
from pathlib import Path
import datetime as dt
import re

import numpy as np
import pandas as pd

OUT_DIR = Path(OUT_DIR)
OUT_DIR.mkdir(parents=True, exist_ok=True)

NEVER = 1e30                   # anything above this is the "never set" flag

# ---- one regex per thing we care about ---------------------------------
RE_VEHICLE   = re.compile(r'^Vehicle Name:\s*(\S+)')
RE_CURRTIME  = re.compile(r'^Curr Time:\s*(.+?)\s+MT:\s*(\d+)')
RE_BECAUSE   = re.compile(r'^Because:\s*(.+?)\s*$')
RE_MISSION   = re.compile(r'^MissionName:\s*(\S+)\s+MissionNum:\s*(\S+)'
                          r'(?:\s*\(([\d.]+)\))?')
RE_ATSURFACE = re.compile(r'^Glider\s+(\S+)\s+at surface')
RE_DR        = re.compile(r'^DR\s+Location:\s*(-?[\d.]+)\s*N\s*(-?[\d.]+)\s*E'
                          r'\s*measured\s*(\S+)\s*secs ago')
RE_GPS       = re.compile(r'^GPS Location:\s*(-?[\d.]+)\s*N\s*(-?[\d.]+)\s*E'
                          r'\s*measured\s*(\S+)\s*secs ago')
RE_SENSOR    = re.compile(r'^\s*sensor:(\S+?)\(([^)]*)\)\s*=\s*(\S+)'
                          r'\s+(\S+)\s+secs ago')
RE_DEVSUM    = re.compile(r'^devices:\(t/m/s\)\s*errs:\s*(\d+)\s*/\s*(\d+)\s*/'
                          r'\s*(\d+)\s*warn:\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)'
                          r'\s*odd:\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)')
RE_DEVROW    = re.compile(r'^\s*(\d+)\s+(\S+)\s+(.*?)\s*$')
RE_BRACKET   = re.compile(r'\[\s*(\d+)\s+(\d+)\s+(\d+)\s*\]')
RE_ABORT     = re.compile(r'^ABORT HISTORY:\s*(.+?):\s*(.+?)\s*$')
RE_WAYPOINT  = re.compile(r'^Waypoint:\s*\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)'
                          r'\s*Range:\s*(\d+)\s*m,\s*Bearing:\s*(\d+)\s*deg,'
                          r'\s*Age:\s*(\S+)')
RE_ZSTART    = re.compile(r'Starting zModem transfer of (\S+) to/from \S+'
                          r'\s+size is\s+(\d+)')
RE_ZDONE     = re.compile(r'zModem transfer DONE for file (\S+)')
RE_DIVEIN    = re.compile(r'^Time until diving is:\s*(\d+)')
RE_DISKFREE  = re.compile(r'^Megabytes available on c:\s*=\s*([\d.]+)')
RE_DISKUSED  = re.compile(r'^Megabytes used\s+on c:\s*=\s*([\d.]+)')
RE_HEAP      = re.compile(r'M_FREE_HEAP=[\d.]+K\((\d+) bytes\)')
RE_OOD       = re.compile(r':OOD:(\S+?):\s*(.+?)\s*$')
RE_LOGOPEN   = re.compile(r'(\S+\.mcg) LOG FILE (OPENED|CLOSED)')


def nmea_to_deg(x):
    '''Slocum reports DDMM.mmm (1200.748 -> 12 deg 00.748 min). Sign is
    carried on the whole number, so split it off before converting.'''
    try:
        x = float(x)
    except (TypeError, ValueError):
        return np.nan
    if abs(x) > 1e6:                       # 69696969.0 = the "no fix" flag
        return np.nan
    sign = -1.0 if x < 0 else 1.0
    x = abs(x)
    deg = np.floor(x / 100.0)
    return sign * (deg + (x - 100.0 * deg) / 60.0)


def age(x):
    '''"49.658" -> 49.658 ; "1e+308" -> NaN (never set)'''
    try:
        v = float(x)
    except (TypeError, ValueError):
        return np.nan
    return np.nan if abs(v) > NEVER else v


def num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return np.nan
    return np.nan if abs(v) > NEVER else v


def parse_currtime(s):
    '''"Thu Jul 23 10:35:00 2026" -> datetime. Day-of-month can be
    space-padded, so squeeze the whitespace first.'''
    s = re.sub(r'\s+', ' ', s.strip())
    for fmt in ('%a %b %d %H:%M:%S %Y', '%b %d %H:%M:%S %Y',
                '%a %b %d %H:%M:%S %Z %Y'):
        try:
            return dt.datetime.strptime(s, fmt)
        except ValueError:
            continue
    return pd.NaT


#%% ============================================================
#   cut the text into records
#   ============================================================
CTX_LINES = 8      # how far back to look for the "Because:" / "MissionName:"
                   # header that precedes each "Vehicle Name:" dump


def split_records(lines):
    '''-> [(context_lines, body_lines)], one pair per status dump.

    The body runs from "Vehicle Name:" to the next one, so everything that
    happened after the dump (transfers, control-R, housekeeping) is attached
    to the record it followed.'''
    anchors = [i for i, l in enumerate(lines) if RE_VEHICLE.match(l)]
    out = []
    for k, a in enumerate(anchors):
        end = anchors[k + 1] if k + 1 < len(anchors) else len(lines)
        ctx_start = max(0, a - CTX_LINES)
        if k > 0:
            ctx_start = max(ctx_start, anchors[k - 1] + 1)
        out.append((lines[ctx_start:a], lines[a:end]))
    return out


def parse_record(ctx, body, source):
    '''One status dump -> (rec dict, [sensor rows], [device rows]).'''
    rec = {'source': source}

    # ---- header lines that sit ABOVE "Vehicle Name:" --------------------
    for l in ctx:
        m = RE_ATSURFACE.match(l)
        if m:
            rec['at_surface'] = True
        m = RE_BECAUSE.match(l)
        if m:
            rec['because'] = m.group(1)
        m = RE_MISSION.match(l)
        if m:
            rec['mission_name'] = m.group(1)
            rec['mission_num'] = m.group(2)
            rec['segment'] = m.group(3)

    sensors, devices = [], []
    transfers_started, transfers_done, oods, aborts = [], [], [], {}
    logs_opened, logs_closed = [], []

    for l in body:
        m = RE_VEHICLE.match(l)
        if m:
            rec['vehicle'] = m.group(1); continue

        m = RE_CURRTIME.match(l)
        if m:
            rec['time'] = parse_currtime(m.group(1))
            rec['mt'] = int(m.group(2)); continue

        m = RE_DR.match(l)
        if m:
            rec['dr_lat'] = nmea_to_deg(m.group(1))
            rec['dr_lon'] = nmea_to_deg(m.group(2))
            rec['dr_age_s'] = age(m.group(3)); continue

        m = RE_GPS.match(l)              # TooFar / Invalid do not match
        if m:
            rec['gps_lat'] = nmea_to_deg(m.group(1))
            rec['gps_lon'] = nmea_to_deg(m.group(2))
            rec['gps_age_s'] = age(m.group(3)); continue

        m = RE_SENSOR.match(l)
        if m:
            sensors.append(dict(sensor=m.group(1), units=m.group(2),
                                value=num(m.group(3)),
                                raw=m.group(3), age_s=age(m.group(4))))
            continue

        m = RE_DEVSUM.match(l)
        if m:
            g = [int(x) for x in m.groups()]
            (rec['err_total'], rec['err_mission'], rec['err_segment'],
             rec['warn_total'], rec['warn_mission'], rec['warn_segment'],
             rec['odd_total'], rec['odd_mission'], rec['odd_segment']) = g
            continue

        m = RE_ABORT.match(l)
        if m:
            aborts[m.group(1).strip().replace(' ', '_')] = m.group(2)
            continue

        m = RE_WAYPOINT.match(l)
        if m:
            rec['wpt_lat'] = nmea_to_deg(m.group(1))
            rec['wpt_lon'] = nmea_to_deg(m.group(2))
            rec['wpt_range_m'] = int(m.group(3))
            rec['wpt_bearing_deg'] = int(m.group(4))
            rec['wpt_age'] = m.group(5); continue

        m = RE_ZSTART.search(l)
        if m:
            transfers_started.append((m.group(1), int(m.group(2)))); continue

        m = RE_ZDONE.search(l)
        if m:
            transfers_done.append(m.group(1)); continue

        m = RE_DIVEIN.match(l)
        if m:
            rec['dive_in_s'] = int(m.group(1)); continue

        m = RE_DISKFREE.match(l)
        if m:
            rec['disk_free_mb'] = float(m.group(1)); continue

        m = RE_DISKUSED.match(l)
        if m:
            rec['disk_used_mb'] = float(m.group(1)); continue

        m = RE_HEAP.search(l)
        if m:
            rec['free_heap_bytes'] = int(m.group(1)); continue

        m = RE_OOD.search(l)
        if m:
            oods.append(f'{m.group(1)}: {m.group(2)}'); continue

        m = RE_LOGOPEN.search(l)
        if m:
            (logs_opened if m.group(2) == 'OPENED'
             else logs_closed).append(m.group(1))
            continue

        # ---- device table rows ------------------------------------------
        d = parse_device_row(l)
        if d:
            devices.append(d)
            continue

        # ---- free-text events -------------------------------------------
        if 'RESUMING MISSION' in l:
            rec['resumed'] = True
        if 'MISSION ABORTED' in l or 'ABORTING MISSION' in l:
            rec['aborted_now'] = True
        if 'Quitting mission' in l or 'GliderDos' in l and 'Hit Control' not in l:
            rec.setdefault('to_gliderdos', True)
        if 'CONSCI REQUESTED' in l:
            rec['consci'] = True
        if 'GLD: SUCCESS' in l:
            rec['gld_transfer_ok'] = True
        if 'SCI: SUCCESS' in l:
            rec['sci_transfer_ok'] = True

    # ---- roll the lists up into scalar columns --------------------------
    rec['n_files_sent'] = len(transfers_done)
    rec['bytes_sent'] = int(sum(sz for _, sz in transfers_started)) or 0
    rec['files_sent'] = ' '.join(transfers_done)
    rec['n_ood'] = len(oods)
    rec['ood'] = ' | '.join(dict.fromkeys(oods))     # dedupe, keep order
    rec['log_files'] = ' '.join(dict.fromkeys(logs_opened + logs_closed))
    for k, v in aborts.items():
        rec['abort_' + k] = v

    return rec, sensors, devices


def parse_device_row(l):
    '''  6            GPS  I u  -1  20   5  0 [ 0 0 0] [ 5 2 0] [ 0 0 0]
    -> dict, or None if the line is not a device row. The three bracket
    groups are errors, warnings, oddities, each as total/mission/segment.'''
    m = RE_DEVROW.match(l)
    if not m:
        return None
    idx, name, rest = int(m.group(1)), m.group(2), m.group(3)
    if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*\*?$', name):
        return None                       # not a device name -> not our line
    if rest.strip() == '-':
        return dict(dev_index=idx, device=name.rstrip('*'),
                    critical=name.endswith('*'), installed=False,
                    in_use=False,
                    err_total=0, err_mission=0, err_segment=0,
                    warn_total=0, warn_mission=0, warn_segment=0,
                    odd_total=0, odd_mission=0, odd_segment=0)
    if not rest.startswith('I'):
        return None                       # installed flag is always I or -
    parts = rest.split()
    counts = RE_BRACKET.findall(rest)
    if len(counts) not in (0, 3):
        return None
    z = [(0, 0, 0)] * 3
    if counts:
        z = [tuple(int(x) for x in c) for c in counts]
    return dict(dev_index=idx, device=name.rstrip('*'),
                critical=name.endswith('*'), installed=True,
                in_use=(len(parts) > 1 and parts[1] == 'u'),
                err_total=z[0][0], err_mission=z[0][1], err_segment=z[0][2],
                warn_total=z[1][0], warn_mission=z[1][1], warn_segment=z[1][2],
                odd_total=z[2][0], odd_mission=z[2][1], odd_segment=z[2][2])


#%% ============================================================
#   file -> dataframes
#   ============================================================
def parse_file(path):
    text = Path(path).read_text(errors='replace')
    lines = text.splitlines()
    recs, sens, devs = [], [], []
    for ctx, body in split_records(lines):
        r, s, d = parse_record(ctx, body, Path(path).name)
        if pd.isna(r.get('time', pd.NaT)):
            continue                      # a dump without a usable timestamp
        recs.append(r)
        for row in s:
            sens.append({**row, 'time': r['time'],
                         'mission_num': r.get('mission_num')})
        for row in d:
            devs.append({**row, 'time': r['time'],
                         'mission_num': r.get('mission_num')})
    return recs, sens, devs


def find_logs(glider):
    '''Everything in data/<glider>-logs/. The folder is already per glider,
    so no name filtering is needed - and dockserver dialogs are named by
    date or segment far more often than by vehicle. Records that turn out
    to belong to another glider are dropped later on "Vehicle Name:".'''
    return config.find_glider_logs(glider)


#%% ============================================================
#   post-processing: deltas and grouping
#   ============================================================
def finish_surfacings(df):
    '''sort, group consecutive dumps of the same segment, add deltas'''
    df = df.sort_values('time').reset_index(drop=True)

    for col in ('n_files_sent', 'bytes_sent', 'n_ood'):
        if col not in df:
            df[col] = 0
    for col in ('err_total', 'warn_total', 'odd_total'):
        if col not in df:
            df[col] = np.nan

    # a surfacing = consecutive records sharing a mission_num
    mn = df.get('mission_num', pd.Series([None] * len(df)))
    df['surfacing_id'] = (mn != mn.shift()).cumsum()
    df['dump_in_surfacing'] = df.groupby('surfacing_id').cumcount() + 1
    df['last_dump'] = (df['surfacing_id'] != df['surfacing_id'].shift(-1))

    # NEW problems since the previous dump. Counters reset when the glider
    # resets, so a negative diff means "reset", not "-3 errors".
    for kind in ('err', 'warn', 'odd'):
        d = df[f'{kind}_total'].diff()
        df[f'new_{kind}'] = d.clip(lower=0).fillna(0).astype('Int64')

    df['severity'] = np.select(
        [df['new_err'].fillna(0) > 0,
         df['new_warn'].fillna(0) > 0,
         df['new_odd'].fillna(0) > 0],
        ['error', 'warning', 'oddity'], default='ok')
    return df


def finish_devices(df):
    '''per-device delta of the cumulative totals'''
    if df.empty:
        return df
    df = df.sort_values(['device', 'time']).reset_index(drop=True)
    for kind in ('err', 'warn', 'odd'):
        d = df.groupby('device')[f'{kind}_total'].diff()
        df[f'new_{kind}'] = d.clip(lower=0).fillna(0).astype(int)
    return df.sort_values(['time', 'dev_index']).reset_index(drop=True)


#%% ============================================================
#   run
#   ============================================================
def build(glider):
    print(f'\n=== {glider} ===')
    files = find_logs(glider)

    if not files:
        return None

    recs, sens, devs = [], [], []
    for p in files:
        r, s, d = parse_file(p)
        if len(r) < MIN_RECORDS:
            print(f'   {p.name}: no status dumps found')
        recs += r; sens += s; devs += d

    if not recs:
        print('   nothing parsed')
        return None

    surf = finish_surfacings(pd.DataFrame(recs))
    # keep only this glider if the files were mixed
    if 'vehicle' in surf:
        keep = surf['vehicle'].str.lower() == glider.lower()
        if keep.any():
            surf = surf[keep].reset_index(drop=True)

    sensors = pd.DataFrame(sens)
    if not sensors.empty:
        sensors = sensors.sort_values(['time', 'sensor']).reset_index(drop=True)
        if DROP_STALE_SENSORS:
            sensors['stale'] = ~np.isfinite(sensors['age_s'])
        # the moment the value was actually measured, not reported
        sensors['measured_at'] = sensors['time'] - pd.to_timedelta(
            sensors['age_s'].fillna(0), unit='s')

    devices = finish_devices(pd.DataFrame(devs))

    print(f'   {len(surf)} status dumps, {surf["surfacing_id"].nunique()} '
          f'surfacings, {surf["time"].min()} -> {surf["time"].max()}')
    if not sensors.empty:
        print(f'   {len(sensors)} sensor readings, '
              f'{sensors["sensor"].nunique()} distinct sensors')
    if not devices.empty:
        n = int((devices[['new_err', 'new_warn', 'new_odd']].sum(axis=1) > 0).sum())
        print(f'   {len(devices)} device rows, {n} with something NEW')
    bad = surf[surf['severity'] != 'ok']
    if len(bad):
        print(f'   !! {len(bad)} dumps introduced new problems:')
        for _, r in bad.tail(5).iterrows():
            print(f'      {r["time"]}  {r["severity"]:8s} '
                  f'err+{r["new_err"]} warn+{r["new_warn"]} odd+{r["new_odd"]}')

    stem = OUT_DIR / glider
    if WRITE_PARQUET:
        try:
            surf.to_parquet(f'{stem}_surfacings.parquet', index=False)
            if not sensors.empty:
                sensors.to_parquet(f'{stem}_sensors.parquet', index=False)
            if not devices.empty:
                devices.to_parquet(f'{stem}_devices.parquet', index=False)
            print(f'   -> {stem}_*.parquet')
        except ImportError:
            print('   pyarrow not installed - `pip install pyarrow` for parquet')
    if WRITE_CSV:
        surf.to_csv(f'{stem}_surfacings.csv', index=False)
        print(f'   -> {stem}_surfacings.csv')
    return surf, sensors, devices


# %%
if __name__ == '__main__':
    for g in GLIDERS:
        build(g)
# %%