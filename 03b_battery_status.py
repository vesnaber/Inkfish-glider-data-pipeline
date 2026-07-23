'''
03b_battery.py
Battery state and endurance projections, computed from the parsed surface
dialogs and written out as JSON + parquet for anything downstream (the Logs
/ Battery tab in 04, the Flask app, an alert email, whatever).

Runs after 03_parse_logs.py, before 04_interactive_html.py.

Everything is measured from the glider where possible, with the JSON files
as the fallback and as the lookup table:

  BATTERY PACK   implied capacity = amphr_total / (1 - relative_charge/100)
                 matched against f_coulomb_battery_capacity in
                 battery_types.json. On the test deployment this comes out
                 at 215.000 Ah and lands exactly on "lithium rechargeable
                 standard" - the glider's own coulomb counter and its own
                 percentage are consistent by construction, so this is a
                 lookup rather than an estimate.

  FLIGHT CONFIG  the buoyancy swing (c_climb_bpump - c_dive_bpump, which
                 agrees with c_autoballast_volume), u_low_power_cycle_time
                 and whether science is on, matched against the
                 descriptions in battery_scenarios.json.

  CONSUMPTION    per dive, from the amp-hour counter differenced between
                 consecutive surfacings. Early on there are too few dives
                 for that to mean anything, so the projection falls back to
                 the book figure for the detected config and switches over
                 once MIN_DIVES_FOR_MEASURED dives are in.

  THRESHOLDS     recommended_recovery / critical_recovery / shutdown
                 fractions from battery_types.json, as fractions of
                 f_coulomb_battery_capacity USED. For the lithium standard
                 pack that is 84 % used = 16 % left (start recovery),
                 88 % = 12 % left (critical), 100 % = flat.

    python 03b_battery.py
'''
#%% ============================================================
#   SETTINGS
#   ============================================================
import config

GLIDERS = [config.GLIDER]

LOG_DIR = config.L0_LOGS          # parquet from 03_parse_logs.py
OUT_DIR = config.L0_LOGS          # battery JSON + parquet go next to it

TYPES_JSON     = config.ROOT / 'battery_types.json'
SCENARIOS_JSON = config.ROOT / 'battery_scenarios.json'

# ---- what to assume before there is enough data -------------------------
DEFAULT_BATTERY = 'lithium rechargeable standard'
DEFAULT_CONFIG  = 'normal_flight'    # full science, 400cc, low power 0s
MIN_DIVES_FOR_MEASURED = 6           # below this the measured rate is noise,
                                     # so the headline projection uses the
                                     # book figure for the detected config

# ---- sensor names in the surface dialog ---------------------------------
S_AMPHR   = 'm_coulomb_amphr_total'  # cumulative Ah used - the primary signal
S_PCT     = 'm_lithium_battery_relative_charge'
S_VOLTS   = 'm_battery'
S_DIVE_CC = 'c_dive_bpump'           # negative, cc
S_CLIMB_CC = 'c_climb_bpump'         # positive, cc
S_BALLAST = 'c_autoballast_volume'   # cc, agrees with the swing above
S_LOWPWR  = 'u_low_power_cycle_time' # sec; <= 0 means low power is off
S_SCIENCE = 'c_science_on'

# ---- rate windows -------------------------------------------------------
RATE_WINDOWS_DAYS = [1, 3, 7]        # trailing windows for the Ah/day fits
HEADLINE_WINDOW_DAYS = 3             # which one drives "as flying now"
MIN_POINTS_FOR_FIT = 4

# ---- sanity filters -----------------------------------------------------
MAX_AH_PER_DIVE = 20.0               # a bigger jump is a counter glitch or a
                                     # missed surfacing, not one dive
MIN_DIVE_HOURS = 0.3
MAX_DIVE_HOURS = 30.0

SPIKE_WINDOW = 9
SPIKE_MAD_K = 6.0
MIN_SPIKE_AH = 2.0
RESET_DROP_AH = 5.0
BALLAST_TOL_CC = 60

SURFACE_MERGE_MINUTES = 30
MIN_DIVE_DEPTH_M = 20        # an interval only counts as a DIVE if the glider
                             # actually got below this. Surfacing twice in a
                             # row makes a surface-only interval that costs
                             # almost nothing and lasts minutes; averaging
                             # those in drags the Ah/dive figure down.
RECENT_DIVES = 5             # how many of the most recent dives the headline
                             # rate is taken from (median, so one odd dive
                             # cannot move it)
SHOW_ALL_SCENARIOS = False   # False = project only the config the glider is
                             # actually flying. True = the whole fan.
ROLL_RATE_HOURS = 24
MAKE_FIGURE = True
FIG_DPI = 130
PROJECT_DAYS_MAX = 400               # cap the projection curve length


#%% ============================================================
#   setup
#   ============================================================
from pathlib import Path
import datetime as dt
import json

import numpy as np
import pandas as pd

OUT_DIR = Path(OUT_DIR)
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path, key):
    p = Path(path)
    if not p.exists():
        print(f'   MISSING {p.name} - put it in the repo root')
        return []
    return json.loads(p.read_text())[key]


def parse_description(d):
    '''"full science, 400cc, low power 15s" -> (science, cc, low_power_s)'''
    d = d.lower()
    science = 'no science' not in d
    cc = None
    for tok in d.replace(',', ' ').split():
        if tok.endswith('cc') and tok[:-2].isdigit():
            cc = int(tok[:-2])
    lp = None
    if 'low power' in d:
        tail = d.split('low power', 1)[1].split(',')[0].strip()
        for tok in tail.replace('s', ' ').split():
            if tok.isdigit():
                lp = int(tok)
                break
        if lp is None and 'flight' in tail:
            lp = 0
    return science, cc, lp


#%% ============================================================
#   load the parsed logs
#   ============================================================
def load_parsed(glider):
    '''-> (surfacings, wide sensor table indexed by dump time)'''
    d = Path(LOG_DIR)
    surf = d / f'{glider}_surfacings.parquet'
    sens = d / f'{glider}_sensors.parquet'
    if not surf.exists() or not sens.exists():
        print(f'   no parsed logs in {d} - run 03_parse_logs.py first')
        return None, None

    S = pd.read_parquet(surf)
    S['time'] = pd.to_datetime(S['time'])
    V = pd.read_parquet(sens)
    V['time'] = pd.to_datetime(V['time'])

    # one row per dump, one column per sensor
    W = V.pivot_table(index='time', columns='sensor', values='value',
                      aggfunc='last').sort_index()
    return S, W


def load_depth(glider):
    """(times, depth) from the L0 timeseries, for telling dives from surface
    hops. Optional - without it every interval is assumed to be a dive."""
    try:
        import xarray as xr
        p = config.newest_nc(config.L0_TS, glider)
        with xr.open_dataset(p) as ts:
            if 'depth' not in ts:
                print('   no depth in the timeseries - cannot filter hops')
                return None
            t = np.asarray(ts.time.values)
            d = np.asarray(ts.depth.values, float)
        ok = np.isfinite(d)
        order = np.argsort(t[ok])
        return t[ok][order], d[ok][order]
    except Exception as e:
        print(f'   no timeseries depth ({e}) - cannot filter surface hops')
        return None


def clean_series(W, verbose=True):
    '''Dumps that carry a usable amp-hour reading, with the counter
    glitches taken out. Three separate problems, handled separately:

      SPIKES  one dump reporting a wild value. Rejected against a rolling
              median, so a single bad HIGH reading costs one dump instead
              of every dump after it (a "must exceed the running maximum"
              test gets stuck on the spike and bins the rest of the
              deployment).
      RESETS  a large fall means the counter restarted or the battery was
              swapped. Only the latest leg can be projected forward.
      DIPS    sub-Ah wobble from telemetry rounding, smoothed by enforcing
              non-decreasing values sequentially.
    '''
    if S_AMPHR not in W:
        print(f'   no {S_AMPHR} in the logs - cannot project')
        return None
    df = W.copy().sort_index()
    df = df[~df.index.duplicated(keep='last')]
    df = df[np.isfinite(df[S_AMPHR])]
    if df.empty:
        return None
    if len(df) < 3:
        df['elapsed_days'] = (df.index - df.index[0]) / pd.Timedelta('1D')
        return df
    n0 = len(df)

    a = df[S_AMPHR]
    med = a.rolling(SPIKE_WINDOW, center=True, min_periods=3).median()
    resid = a - med
    mad = float((resid - resid.median()).abs().median()) * 1.4826
    tol = max(SPIKE_MAD_K * mad, MIN_SPIKE_AH)
    spike = resid.abs() > tol
    if verbose and spike.any():
        print(f'   {int(spike.sum())} dumps rejected as counter spikes '
              f'(off the local median by > {tol:.2f} Ah)')
    df = df[~spike]

    a = df[S_AMPHR]
    step = a.diff()
    resets = step < -RESET_DROP_AH
    if resets.any():
        if verbose:
            for ti in a.index[resets]:
                print(f'   !! counter RESET at {ti:%Y-%m-%d %H:%M} '
                      f'({step[ti]:+.1f} Ah) - projecting from the '
                      f'latest leg only')
        df = df[df.index >= a.index[resets][-1]]

    vals = df[S_AMPHR].values
    keep = np.ones(len(vals), bool)
    last = vals[0]
    for i in range(1, len(vals)):
        if vals[i] + 1e-9 < last:
            keep[i] = False
        else:
            last = vals[i]
    if verbose and (~keep).sum():
        print(f'   {int((~keep).sum())} dumps with a small counter dip '
              f'smoothed out')
    df = df[keep]

    if verbose:
        print(f'   {len(df)} of {n0} dumps usable, '
              f'{df[S_AMPHR].iloc[0]:.2f} -> {df[S_AMPHR].iloc[-1]:.2f} Ah '
              f'over {(df.index[-1]-df.index[0])/pd.Timedelta("1D"):.2f} d')
    df['elapsed_days'] = (df.index - df.index[0]) / pd.Timedelta('1D')
    return df


#%% ============================================================
#   detection: which pack, which flight config
#   ============================================================
def detect_battery(df, types):
    '''Implied capacity = Ah used / fraction used. The glider computes its
    own percentage from its own coulomb counter, so the ratio recovers the
    f_coulomb_battery_capacity it was configured with - exactly, not
    approximately. Median over all dumps to shrug off rounding.'''
    default = next((b for b in types if b['name'] == DEFAULT_BATTERY),
                   types[0] if types else None)
    if not types:
        return None, None, 'no battery_types.json'
    if S_PCT not in df:
        return default, None, f'no {S_PCT} - using the default'

    d = df[np.isfinite(df[S_PCT])]
    d = d[(d[S_PCT] > 1) & (d[S_PCT] < 99.5) & (d[S_AMPHR] > 0.5)]
    if len(d) < 3:
        return default, None, 'too few paired readings - using the default'

    implied = float(np.median(d[S_AMPHR] / (1 - d[S_PCT] / 100)))
    best = min(types, key=lambda b: abs(b['f_coulomb_battery_capacity']
                                        - implied))
    err = abs(best['f_coulomb_battery_capacity'] - implied)
    tol = 0.02 * best['f_coulomb_battery_capacity']
    if err > tol:
        return (default, implied,
                f'implied {implied:.1f} Ah matches nothing within 2% '
                f'- using the default')
    return best, implied, f'implied {implied:.1f} Ah'


def detect_config(df, scenarios):
    '''Latest ballast swing + low-power setting + science on/off, matched
    against the scenario descriptions. Uses the LAST dump, because the
    config can be changed mid-deployment and only the current one predicts
    the future.'''
    default = next((s for s in scenarios if s['config_name'] == DEFAULT_CONFIG),
                   scenarios[0] if scenarios else None)
    if not scenarios:
        return None, {}, 'no battery_scenarios.json'

    last = df.iloc[-1]
    obs = {}
    # c_autoballast_volume FIRST: it names the volume directly. The pump
    # swing (climb - dive) agrees with it on some gliders and not others,
    # since the commands are in pump counts whose scaling depends on the
    # pump fitted. Both are recorded so a disagreement stays visible.
    if S_BALLAST in df and np.isfinite(last.get(S_BALLAST, np.nan)):
        obs['cc'] = float(last[S_BALLAST])
        obs['cc_source'] = S_BALLAST
    if S_CLIMB_CC in df and S_DIVE_CC in df \
            and np.isfinite(last.get(S_CLIMB_CC, np.nan)) \
            and np.isfinite(last.get(S_DIVE_CC, np.nan)):
        obs['pump_swing'] = float(last[S_CLIMB_CC] - last[S_DIVE_CC])
        obs.setdefault('cc', obs['pump_swing'])
        obs.setdefault('cc_source', 'pump swing')
    if S_LOWPWR in df and np.isfinite(last.get(S_LOWPWR, np.nan)):
        v = float(last[S_LOWPWR])
        obs['low_power_s'] = 0 if v <= 0 else v
    if S_SCIENCE in df and np.isfinite(last.get(S_SCIENCE, np.nan)):
        obs['science'] = bool(last[S_SCIENCE])
    else:
        obs['science'] = True          # science sensors are being reported

    if 'cc' not in obs:
        return default, obs, 'no ballast reading - using the default'

    scored = []
    for s in scenarios:
        sci, cc, lp = parse_description(s['description'])
        pts = 0
        if cc is not None and abs(cc - obs['cc']) < BALLAST_TOL_CC:
            pts += 2
        if lp is not None and 'low_power_s' in obs \
                and abs(lp - obs['low_power_s']) < 1:
            pts += 1
        if sci == obs.get('science', True):
            pts += 1
        scored.append((pts, s))
    scored.sort(key=lambda x: -x[0])
    if scored[0][0] < 2:               # ballast did not match anything
        return default, obs, (f'{obs["cc"]:.0f} cc matches no scenario '
                              f'- using the default')
    return scored[0][1], obs, f'{obs["cc"]:.0f} cc'


#%% ============================================================
#   measured consumption
#   ============================================================
def collapse_to_surfacings(df, gap_minutes=SURFACE_MERGE_MINUTES):
    """One row per SURFACING, not per dump.

    The glider reprints the whole status block every ~60 s for as long as it
    sits at the surface, so consecutive dumps are minutes apart. Differencing
    those gives fragments of surface time, not dives - which is why most of
    them then fail the dive-length sanity check. A dump is the last of its
    surfacing when the next dump is more than `gap_minutes` away; keeping
    those gives the most recent reading from each surfacing.
    """
    if len(df) < 2:
        return df
    nxt = df.index.to_series().diff().shift(-1)
    is_last = nxt.isna() | (nxt > pd.Timedelta(minutes=gap_minutes))
    return df[is_last.values]


def per_dive(df, depth=None, verbose=True):
    """One row per DIVE: how long it took and how much it cost.

    A surfacing-to-surfacing interval is only a dive if the glider actually
    went down in between. When it surfaces twice in a row - a comms retry, a
    missed waypoint - the interval is minutes long and costs almost nothing,
    and averaging those in drags Ah/dive towards zero. With the timeseries
    depth available they are rejected outright; without it, only the length
    sanity check applies and the figure says so.

    dive_hours and ah_per_dive are exactly the quantities
    battery_scenarios.json is written in, so measured and book values sit
    side by side.
    """
    s = collapse_to_surfacings(df)
    if verbose:
        print(f'   {len(df)} dumps -> {len(s)} surfacings '
              f'(merged within {SURFACE_MERGE_MINUTES} min)')
    if len(s) < 2:
        return pd.DataFrame(columns=['end', 'dive_hours', 'ah_per_dive',
                                     'ah_per_day', 'max_depth'])

    hrs = np.diff(s.index.values) / np.timedelta64(1, 'h')
    ah = np.diff(s[S_AMPHR].values)
    out = pd.DataFrame({'start': s.index[:-1], 'end': s.index[1:],
                        'dive_hours': hrs, 'ah_per_dive': ah})

    out['max_depth'] = np.nan
    if depth is not None:
        tv, dv = depth
        for i, (a, b) in enumerate(zip(out.start.values, out.end.values)):
            i0, i1 = np.searchsorted(tv, [a, b])
            if i1 > i0:
                out.loc[i, 'max_depth'] = float(np.nanmax(dv[i0:i1]))

    sane = (out.dive_hours.between(MIN_DIVE_HOURS, MAX_DIVE_HOURS)
            & out.ah_per_dive.between(0, MAX_AH_PER_DIVE))
    if depth is not None:
        deep = out.max_depth >= MIN_DIVE_DEPTH_M
        n_hop = int((sane & ~deep.fillna(False)).sum())
        if verbose and n_hop:
            print(f'   {n_hop} surface-only intervals rejected '
                  f'(never got below {MIN_DIVE_DEPTH_M} m)')
        ok = sane & deep.fillna(False)
    else:
        ok = sane

    n_bad = int((~sane).sum())
    if verbose and n_bad:
        print(f'   {n_bad} intervals rejected as too short/long '
              f'or a counter jump')
    out = out[ok].reset_index(drop=True)
    out['ah_per_day'] = out.ah_per_dive * 24 / out.dive_hours
    if verbose:
        print(f'   {len(out)} real dives')
    return out


def rolling_rate(df, hours=ROLL_RATE_HOURS):
    """Observed Ah/day in a trailing window, as a series - the thing that
    shows a config change actually taking effect."""
    a = df[S_AMPHR]
    t = df.index
    out = []
    for i in range(len(a)):
        m = (t >= t[i] - pd.Timedelta(hours=hours)) & (t <= t[i])
        if m.sum() < 2:
            out.append(np.nan)
            continue
        span = (t[m][-1] - t[m][0]) / pd.Timedelta('1D')
        out.append((a[m].iloc[-1] - a[m].iloc[0]) / span
                   if span > 0.2 else np.nan)
    return pd.Series(out, index=t, name='ah_per_day')


def fit_voltage(df, bat):
    """Straight line through the pack voltage, projected to the abort and
    cutoff levels - the same check the MATLAB does.

    Kept as a CROSS-CHECK only, never as the headline. Lithium packs hold
    voltage almost flat and then fall off a cliff, so a linear fit reads
    optimistic right up until it does not. The coulomb counter is the
    trustworthy signal; this is here to disagree with it loudly if the
    pack is behaving unexpectedly.
    """
    if S_VOLTS not in df:
        return None
    d = df[np.isfinite(df[S_VOLTS])]
    if len(d) < MIN_POINTS_FOR_FIT or np.ptp(d.elapsed_days.values) <= 0:
        return None
    x = d.elapsed_days.values
    y = d[S_VOLTS].values
    slope, icept = np.polyfit(x, y, 1)
    pred = slope * x + icept
    ss = np.sum((y - y.mean()) ** 2)
    r2 = 1 - np.sum((y - pred) ** 2) / ss if ss > 0 else 1.0
    now_day = float(d.elapsed_days.iloc[-1])
    t0 = d.index[0]
    out = dict(volts_per_day=float(slope), intercept=float(icept),
               n=int(len(d)), r2=float(r2), now_volts=float(y[-1]))
    for key, level in (('undervolts', bat['undervolts']),
                       ('cutoff', bat['Vcutoff'])):
        if slope < 0:
            day = (level - icept) / slope
            out[key] = dict(volts=level, days=float(day - now_day),
                            date=(t0 + pd.Timedelta(days=day)).isoformat())
        else:
            out[key] = dict(volts=level, days=None, date=None)
    return out


def fit_rate(df, days=None):
    '''Ah/day from a straight line through the counter. Returns
    (rate, intercept, n, r2) or None.'''
    d = df
    if days is not None:
        d = df[df.elapsed_days >= df.elapsed_days.iloc[-1] - days]
    if len(d) < MIN_POINTS_FOR_FIT:
        return None
    x = d.elapsed_days.values
    y = d[S_AMPHR].values
    if np.ptp(x) <= 0:
        return None
    slope, icept = np.polyfit(x, y, 1)
    pred = slope * x + icept
    ss = np.sum((y - y.mean()) ** 2)
    r2 = 1 - np.sum((y - pred) ** 2) / ss if ss > 0 else 1.0
    return dict(ah_per_day=float(slope), intercept=float(icept),
                n=int(len(d)), r2=float(r2))


#%% ============================================================
#   projections
#   ============================================================
def thresholds(bat):
    cap = bat['f_coulomb_battery_capacity']
    return [
        ('recovery', bat['recommended_recovery_fraction_used'],
         'start recovery'),
        ('critical', bat['critical_recovery_fraction_used'],
         'critical - do not plan past this'),
        ('shutdown', bat['shutdown_fraction_used'], 'flat'),
    ], cap


def project(now_t, now_ah, rate, bat):
    '''Days and dates at which a given Ah/day rate reaches each threshold.'''
    ths, cap = thresholds(bat)
    out = {}
    for name, frac, _ in ths:
        target = frac * cap
        if rate is None or rate <= 0:
            out[name] = dict(ah=target, days=None, date=None)
            continue
        days = (target - now_ah) / rate
        out[name] = dict(
            ah=float(target), days=float(days),
            date=(now_t + pd.Timedelta(days=days)).isoformat()
            if abs(days) < PROJECT_DAYS_MAX * 2 else None)
    return out


#%% ============================================================
#   figure - the same three panels as plotBatteryProjection.m,
#   plus the scenario fans
#   ============================================================
def battery_figure(glider, df, dives, out, rates, proj, bat, path):
    '''Three stacked panels: cumulative Ah with the projection fan and the
    recovery / critical / shutdown lines, the observed daily rate, and the
    pack voltage. Saved as a png so it lands in the normal plots folder
    alongside everything 02 makes.'''
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    cap = bat['f_coulomb_battery_capacity']
    now_t = pd.Timestamp(out['now']['time'])
    now_ah = out['now']['ah_used']
    headline = out['headline']

    fig, ax = plt.subplots(3, 1, figsize=(11, 12), sharex=False)

    # ---- 1. cumulative Ah + projections --------------------------------
    a = ax[0]
    a.plot(df.index, df[S_AMPHR], '-', lw=1.6, color='#1f77b4',
           label='measured', zorder=5)
    horizon = max([p['shutdown']['days'] or 0 for p in proj.values()] + [1])
    horizon = min(horizon * 1.15, PROJECT_DAYS_MAX)
    tp = pd.date_range(now_t, now_t + pd.Timedelta(days=horizon), periods=50)
    dd = (tp - now_t) / pd.Timedelta('1D')
    cmap = plt.get_cmap('viridis')
    for i, (name, r) in enumerate(rates.items()):
        y = now_ah + r['ah_per_day'] * dd
        is_head = name == headline
        a.plot(tp, np.where(y <= cap * 1.02, y, np.nan),
               '--', lw=2.4 if is_head else 1.3,
               color='#d62728' if is_head else cmap(i / max(len(rates)-1, 1)),
               label=f'{name} ({r["ah_per_day"]:.1f} Ah/d)',
               zorder=4 if is_head else 3)
    for key, style in (('recovery', ('-', '#e69500')),
                       ('critical', ('-', '#c62828')),
                       ('shutdown', ('--', '#555555'))):
        th = out['thresholds'][key]
        a.axhline(th['ah'], ls=style[0], lw=1.4, color=style[1], alpha=.85)
        a.text(df.index[0], th['ah'], f'  {key} ({th["pct_left"]:.0f}% left)',
               va='bottom', ha='left', fontsize=8.5, color=style[1])
    rec = proj[headline]['recovery']
    if rec['date']:
        rt = pd.Timestamp(rec['date'])
        crit = proj[headline]['critical']
        if crit['date']:
            a.axvspan(rt, pd.Timestamp(crit['date']), color='#c62828',
                      alpha=.13, zorder=1)
        a.axvline(rt, color='#c62828', lw=2, zorder=6)
        a.annotate(f'recover by\n{rt:%d %b %H:%M}\n({rec["days"]:.1f} d)',
                   xy=(rt, cap * .45), fontsize=9, color='#c62828',
                   fontweight='bold', ha='center')
    a.axvline(now_t, color='k', lw=.9, ls=':')
    a.set_ylabel('Ah used')
    a.set_ylim(0, cap * 1.05)
    a.set_title(f'{glider}  -  {bat["name"]} ({cap:.0f} Ah), '
                f'flying {out["config"]["config_name"]}\n'
                f'{now_ah:.1f} Ah used, {out["now"]["pct_left"]:.1f} % left '
                f'after {out["now"]["elapsed_days"]:.1f} d',
                fontsize=11, fontweight='bold')
    a.legend(fontsize=7.5, ncol=2, loc='upper left')
    a.grid(alpha=.3)

    # ---- 2. daily rate --------------------------------------------------
    a = ax[1]
    if out.get('roll_rate'):
        rr = pd.Series(out['roll_rate']['ah_per_day'],
                       index=pd.to_datetime(out['roll_rate']['time']))
        a.plot(rr.index, rr.values, '-', lw=1.2, color='#1f77b4',
               label=f'observed ({ROLL_RATE_HOURS} h window)')
    if len(dives):
        a.plot(dives.end, dives.ah_per_day, '.', ms=5, color='#999999',
               label=f'per dive (n={len(dives)}, surface hops excluded)',
               zorder=2)
        tail = dives.tail(RECENT_DIVES)
        a.plot(tail.end, tail.ah_per_day, 'o', ms=6, mfc='none',
               mec='#d62728', mew=1.4,
               label=f'last {RECENT_DIVES} (drives the projection)', zorder=3)
    for w in RATE_WINDOWS_DAYS + ['mission']:
        k = f'{w}d' if w != 'mission' else 'mission'
        f = out['fits'].get(k)
        if f:
            a.axhline(f['ah_per_day'], ls='--', lw=1.1,
                      label=f'{k} fit: {f["ah_per_day"]:.2f}')
    for name, r in rates.items():
        if r.get('kind') == 'scenario':
            a.axhline(r['ah_per_day'], ls=':', lw=.9, color='#bbbbbb')
            a.text(df.index[-1], r['ah_per_day'], f' {name}', fontsize=7,
                   va='center', color='#888888')
    a.set_ylabel('Ah / day')
    a.set_title('consumption rate', fontsize=10)
    a.legend(fontsize=7.5, ncol=2, loc='upper left')
    a.grid(alpha=.3)

    # ---- 3. voltage -----------------------------------------------------
    a = ax[2]
    if S_VOLTS in df:
        a.plot(df.index, df[S_VOLTS], '-', lw=1.3, color='#1f77b4',
               label='pack voltage')
    for key, col in (('undervolts', '#e69500'), ('Vcutoff', '#c62828')):
        a.axhline(bat[key], ls='--', lw=1.3, color=col,
                  label=f'{key} {bat[key]} V')
    v = out.get('voltage')
    if v and v.get('undervolts', {}).get('date'):
        a.set_title(f'voltage  -  linear fit reaches undervolts '
                    f'{v["undervolts"]["date"][:16]} '
                    f'({v["undervolts"]["days"]:.0f} d). Cross-check only: '
                    f'lithium holds flat then falls off a cliff.',
                    fontsize=9)
    else:
        a.set_title('voltage', fontsize=10)
    a.set_ylabel('volts')
    a.set_xlabel('time')
    a.legend(fontsize=7.5, loc='lower left')
    a.grid(alpha=.3)

    for x in ax:
        x.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    fig.tight_layout()
    fig.savefig(path, dpi=FIG_DPI)
    # plt.close(fig)
    print(f'   -> {path}')


def build(glider):
    print(f'\n=== {glider} ===')
    types = load_json(TYPES_JSON, 'battery_types')
    scenarios = load_json(SCENARIOS_JSON, 'operational_scenarios')

    S, W = load_parsed(glider)
    if W is None:
        return None
    df = clean_series(W)
    if df is None or len(df) < 2:
        print('   not enough amp-hour readings yet')
        return None

    bat, implied, bat_why = detect_battery(df, types)
    if bat is None:
        return None
    scen, obs, cfg_why = detect_config(df, scenarios)
    cap = bat['f_coulomb_battery_capacity']

    now_t = df.index[-1]
    now_ah = float(df[S_AMPHR].iloc[-1])
    now_pct = (float(df[S_PCT].iloc[-1]) if S_PCT in df
               and np.isfinite(df[S_PCT].iloc[-1])
               else 100 * (1 - now_ah / cap))
    now_v = (float(df[S_VOLTS].iloc[-1]) if S_VOLTS in df
             and np.isfinite(df[S_VOLTS].iloc[-1]) else None)
    elapsed = float(df.elapsed_days.iloc[-1])

    print(f'   pack   : {bat["name"]}  ({cap:.0f} Ah)   [{bat_why}]')
    print(f'   config : {scen["config_name"]}  '
          f'({scen["description"]})   [{cfg_why}]')
    print(f'   now    : {now_ah:.2f} Ah used, {now_pct:.1f} % left, '
          f'{now_v if now_v is None else round(now_v, 2)} V, '
          f'day {elapsed:.2f} of the record')

    depth = load_depth(glider)
    dives = per_dive(df, depth)
    volt = fit_voltage(df, bat)
    rr = rolling_rate(df)
    fits = {f'{w}d': fit_rate(df, w) for w in RATE_WINDOWS_DAYS}
    fits['mission'] = fit_rate(df)

    measured = None
    if len(dives) >= MIN_DIVES_FOR_MEASURED:
        recent = dives.tail(RECENT_DIVES)
        measured = dict(
            recent=dict(
                dive_hours=float(recent.dive_hours.median()),
                ah_per_dive=float(recent.ah_per_dive.median()),
                ah_per_day=float(recent.ah_per_day.median()),
                ah_per_hour=float((recent.ah_per_dive
                                   / recent.dive_hours).median()),
                n_dives=int(len(recent))),
            all=dict(
                dive_hours=float(dives.dive_hours.median()),
                ah_per_dive=float(dives.ah_per_dive.median()),
                ah_per_day=float(dives.ah_per_day.median()),
                ah_per_hour=float((dives.ah_per_dive
                                   / dives.dive_hours).median()),
                n_dives=int(len(dives))))
        for lab, m in (('last %d' % RECENT_DIVES, measured['recent']),
                       ('all', measured['all'])):
            print(f'   measured ({lab:>7s} dives, n={m["n_dives"]:>3d}): '
                  f'{m["dive_hours"]:5.2f} h/dive, '
                  f'{m["ah_per_dive"]:6.3f} Ah/dive, '
                  f'{m["ah_per_hour"]:5.3f} Ah/h '
                  f'-> {m["ah_per_day"]:6.2f} Ah/day')
    else:
        print(f'   only {len(dives)} real dives, need '
              f'{MIN_DIVES_FOR_MEASURED} - projecting from the book figure')

    # ---- every rate worth plotting -------------------------------------
    rates = {}
    hw = fits.get(f'{HEADLINE_WINDOW_DAYS}d') or fits.get('mission')
    if hw:
        rates['counter fit'] = dict(
            ah_per_day=hw['ah_per_day'], kind='measured',
            note=f'straight line through the Ah counter, last '
                 f'{HEADLINE_WINDOW_DAYS} d, n={hw["n"]}, r2={hw["r2"]:.4f}')
    if measured:
        rates[f'last {RECENT_DIVES} dives'] = dict(
            ah_per_day=measured['recent']['ah_per_day'], kind='measured',
            note=f'{measured["recent"]["ah_per_dive"]:.3f} Ah over '
                 f'{measured["recent"]["dive_hours"]:.2f} h, median')
        rates['all dives'] = dict(
            ah_per_day=measured['all']['ah_per_day'], kind='measured',
            note=f'median of {measured["all"]["n_dives"]} dives')
    # only the config the glider is actually flying - the other three are
    # answers to a question nobody asked unless you are planning a change
    for s in scenarios:
        if SHOW_ALL_SCENARIOS or s['config_name'] == scen['config_name']:
            rates[f'book: {s["config_name"]}'] = dict(
                ah_per_day=s['ah_per_dive'] * 24 / s['dive_hours'],
                kind='scenario', note=s['description'],
                current=(s['config_name'] == scen['config_name']))

    headline = (f'last {RECENT_DIVES} dives' if measured
                else f'book: {scen["config_name"]}')

    proj = {k: project(now_t, now_ah, v['ah_per_day'], bat)
            for k, v in rates.items()}

    print(f'\n   {"rate":22s} {"Ah/day":>7s} {"recovery":>10s} '
          f'{"critical":>10s}   recovery date')
    for k, v in rates.items():
        p = proj[k]['recovery']
        c = proj[k]['critical']
        mark = ' *' if k == headline else '  '
        pd_ = '' if p['days'] is None else f'{p["days"]:8.1f}d'
        cd_ = '' if c['days'] is None else f'{c["days"]:9.1f}d'
        dt_ = '' if p['date'] is None else p['date'][:16]
        print(f'  {mark}{k:20s} {v["ah_per_day"]:7.2f} {pd_:>9s} {cd_:>10s}'
              f'   {dt_}')

    # ---- write ----------------------------------------------------------
    out = dict(
        glider=glider,
        generated=dt.datetime.now().isoformat(timespec='seconds'),
        battery=dict(**bat, implied_capacity_ah=implied, detection=bat_why),
        config=dict(**scen, detection=cfg_why, observed=obs),
        now=dict(time=now_t.isoformat(), ah_used=now_ah, pct_left=now_pct,
                 volts=now_v, elapsed_days=elapsed,
                 first_time=df.index[0].isoformat()),
        thresholds={n: dict(fraction_used=f, ah=f * cap,
                            pct_left=100 * (1 - f), label=lab)
                    for n, f, lab in thresholds(bat)[0]},
        fits=fits, measured=measured, rates=rates, projections=proj,
        headline=headline, n_dives=int(len(dives)), voltage=volt,
        roll_rate=dict(time=[t.isoformat() for t in rr.index],
                       ah_per_day=[None if not np.isfinite(v) else round(float(v), 4)
                                   for v in rr.values]))

    if volt and volt.get('undervolts', {}).get('days') is not None:
        print(f'\n   voltage cross-check: {volt["now_volts"]:.2f} V now, '
              f'linear fit hits undervolts ({bat["undervolts"]} V) in '
              f'{volt["undervolts"]["days"]:.0f} d '
              f'(r2={volt["r2"]:.3f}) - lithium holds flat then drops, '
              f'so treat this as a floor, not a forecast')

    (OUT_DIR / f'{glider}_battery.json').write_text(
        json.dumps(out, indent=2, default=str))
    series = df[[c for c in (S_AMPHR, S_PCT, S_VOLTS) if c in df]].copy()
    series['elapsed_days'] = df.elapsed_days
    series.to_parquet(OUT_DIR / f'{glider}_battery_series.parquet')
    dives.to_parquet(OUT_DIR / f'{glider}_battery_dives.parquet', index=False)
    if MAKE_FIGURE:
        try:
            battery_figure(glider, df, dives, out, rates, proj, bat,
                           config.PLOTS / f'{glider}_battery.png')
        except Exception as e:
            print(f'   figure failed: {e}')
    print(f'\n   -> {OUT_DIR / f"{glider}_battery.json"}')
    print(f'   -> {glider}_battery_series.parquet, '
          f'{glider}_battery_dives.parquet')
    return out


# %%
if __name__ == '__main__':
    for g in GLIDERS:
        build(g)
# %%