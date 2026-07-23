'''
04_interactive_html.py
One self-contained web page per glider (no server - just open the html).

  SECTIONS  - contour (filled + lines) depth-vs-time panels on a uniform
              time axis. Dashed grey vertical lines mark the profiles that
              were really measured, down to the deepest bin they reached;
              everything between them is interpolated. Gaps longer than
              MAX_GAP_HOURS stay empty. Each panel zooms on its own.
  SCIENCE   - scatter (pick x / y / colour) + a T-S diagram with potential
              density isolines.
  GLIDER    - engineering variables stacked against time, measured over
              commanded, with the dive phases shaded.
  3D        - bathymetry as terrain with the section hung along the track as
              a curtain. Unmeasured parts are transparent. The slider picks
              a time RANGE.
  MAP       - bathymetry image + track + depth-averaged current arrows,
              and a current rose.

    python 04_interactive_html.py
'''
#%% ============================================================
#   SETTINGS
#   ------------------------------------------------------------
#   The six you will change most often:
#     GLIDERS, SEGMENTS, SECTION_VARS, REFINE_MINUTES,
#     SECTION_MAX_COLS, N_LEVELS
#   ============================================================
import config

# ---- what to plot -------------------------------------------------------
GLIDERS = [config.GLIDER]   # list of gliders; >1 -> one page each, cross-linked
                            # in the header. e.g. ['unit_398', 'unit_399']

SEGMENTS = None             # which part of the deployment:
                            #   None      -> everything
                            #   43        -> segment 43 only
                            #   (40, 43)  -> segments 40 through 43
                            #   -10       -> the last 10 segments
                            # Smaller window = faster build + smaller html.

MAX_POINTS = 20000          # max samples kept for the Science/Glider/3D-point
                            # tabs. Higher = more detail but heavier page;
                            # thinning is a plain every-Nth stride.

# ---- section panels -----------------------------------------------------
SECTION_VARS = ['temperature', 'salinity', 'potential_density',
                'conductivity', 'chlorophyll', 'oxygen_concentration', 'par']
                            # one panel per variable, in this order. Missing
                            # variables are silently skipped. Also drives the
                            # variable dropdown on the 3D tab.

DERIVE_SALINITY = True      # compute salinity + potential density from
                            # conductivity/temperature with gsw. Needs `gsw`;
                            # without it those two panels disappear.

FILL_GAPS = True            # patch small holes: up to MAX_FILL_BINS empty
                            # depth bins vertically, then between profiles in
                            # time. False = raw grid, much more speckled.
MAX_FILL_BINS = 3           # vertical reach of that patching, in depth bins.

MAX_GAP_HOURS = 6           # NEVER interpolate across a time gap longer than
                            # this (surfacings, comms outages). Those columns
                            # stay NaN and render as blank space.

# ---- section time axis --------------------------------------------------
REFINE_MINUTES = 5          # target spacing of the interpolated columns.
                            # Smaller = smoother contours + bigger file.
                            # None/0 = one column per real profile.

SECTION_MAX_COLS = 600      # hard cap on columns per panel, applied after
                            # REFINE_MINUTES. go.Contour runs marching squares
                            # in JS, so a few thousand columns times ~100 depth
                            # bins is already slow. Raise carefully.

# ---- section rendering --------------------------------------------------
N_LEVELS = 20               # number of filled colour bands (also the number
                            # of discrete steps in the colourscale).
SHOW_CONTOUR_LINES = True   # thin isolines drawn on top of the filled bands.
CONTOUR_LINE_WIDTH = 0.6
CONTOUR_LINE_COLOUR = 'rgba(0,0,0,0.40)'
CONTOUR_LINE_SMOOTHING = 0.85   # 0 = polygonal isolines, 1.3 = very rounded.
CONTOUR_LABELS = False      # numeric labels inline on the isolines; tidy on
                            # one panel, cluttered on seven.
SMOOTH_SECTIONS = False     # True = continuous colourscale instead of
                            # N_LEVELS discrete bands.
SECTION_ROW_HEIGHT = 340    # px per panel; total height scales with the
                            # number of variables.
MIN_LEVEL_SPAN = 1e-9       # if a variable's 2-98 pct range is flatter than
                            # this it is constant, contours would be empty,
                            # so that panel falls back to a heatmap.

SHOW_PROFILE_LINES = True   # dashed vertical line at every REAL profile,
                            # surface -> deepest bin with data. Turn off if
                            # the panels look striped at long deployments.
PROFILE_LINE_COLOUR = 'rgba(110,110,110,0.55)'   # grey
PROFILE_LINE_DASH = 'dash'  # 'solid' | 'dot' | 'dash' | 'longdash' | 'dashdot'
PROFILE_LINE_WIDTH = 1.0
PROFILE_LINE_EVERY = 1      # draw every Nth profile tick (2, 5, 10 ... thins
                            # the stripes without touching the data).

SECTION_DEPTH_STRIDE = 4    # keep every Nth depth bin in the section panels.
                            # The grid is 1 m over ~1100 m = 1100 rows, but a
                            # 340 px panel can only draw ~340. 4 -> 4 m bins,
                            # visually identical, 4x smaller. This is the
                            # single biggest file-size lever.

SECTION_DECIMALS = {        # JSON stores these as text: every decimal place
    'temperature': 3,       # is a character x 1.2M values. Instrument
    'salinity': 3,          # precision is well below these already.
    'potential_density': 2,
    'conductivity': 4,
    'chlorophyll': 4,
    'oxygen_concentration': 2,
    'par': 4,
}
SECTION_DECIMALS_DEFAULT = 3

# ---- colours ------------------------------------------------------------
CMAP_PER_VAR = {'temperature': 'thermal', 'conductivity': 'haline',
                'salinity': 'haline', 'potential_density': 'dense',
                'chlorophyll': 'algae', 'cdom': 'matter',
                'backscatter_700': 'turbid', 'oxygen_concentration': 'oxy',
                'par': 'solar', 'depth': 'deep'}
                            # cmocean name per variable; anything not listed
                            # falls back to 'thermal'. Needs `cmocean`,
                            # otherwise everything becomes Viridis.
CLIM_PCT = (2, 98)          # percentile clipping for every colour limit.
                            # (0, 100) = full range, outliers wash it out.
MARKER_SIZE = 6             # scatter markers (Science / T-S)
MARKER_SIZE_3D = 3          # markers in the 3D point fallback

MARKER_OUTLINE_WIDTH = 0.4  # thin dark ring around every scatter marker.
                            # Several cmocean maps (deep, algae, solar) start
                            # near white, so their lightest values vanish into
                            # the page. The ring keeps every point visible
                            # whatever the colourmap. 0 = no ring.
MARKER_OUTLINE_COLOUR = 'rgba(50,50,50,0.55)'
SCATTER_BG = '#f7f8f9'      # faintly tinted plot background, same reason.
                            # '#ffffff' for pure white.

# ---- Science tab (scatter) ---------------------------------------------
SCIENCE_VARS = ['temperature', 'salinity', 'potential_density', 'conductivity',
                'chlorophyll', 'cdom', 'backscatter_700',
                'oxygen_concentration', 'par', 'depth', 'time',
                'longitude', 'latitude']
DEFAULT_SCIENCE = ('temperature', 'depth')   # (x, y) shown on first load
SCIENCE_HEIGHT = 800
                            # The "colour" dropdown picks which VARIABLE tints
                            # the markers; its colourmap follows from
                            # CMAP_PER_VAR automatically.

# ---- T-S diagram --------------------------------------------------------
TS_DENSITY_CONTOURS = True  # sigma0 isolines in the background (needs gsw)
TS_N_DENSITY_LINES = 12     # roughly how many isolines
TS_COLOUR_BY = 'depth'      # variable used to colour the T-S points
TS_HEIGHT = 780

# ---- Glider tab ---------------------------------------------------------
# One stacked panel per variable, x is always time, all panels share the
# zoom. Where a "commanded_<var>" exists it is drawn UNDER the measured one,
# so the two are directly comparable and the measured trace always wins.
GLIDER_Y_VARS = ['pitch', 'roll', 'heading', 'fin', 'battery_position',
                 'oil_volume', 'altitude']
GLIDER_PAIR_PREFIX = 'commanded_'

GLIDER_ROW_HEIGHT = 150     # px per panel - short on purpose, the point is
                            # to scan many variables at once
GLIDER_DEPTH_ROW_HEIGHT = 190   # the depth panel at the top, a bit taller

GLIDER_MEASURED_COLOUR  = "#ff7e1c"   # light orange - what the glider did
GLIDER_COMMANDED_COLOUR = "#444444"   # dark - what it was told to do
GLIDER_LINE_WIDTH = 1.2
GLIDER_MARKER_SIZE = 3      # 0 = lines only

# dive phases: grey band + white depth line while descending,
# white band + grey depth line while ascending
SHOW_DIVE_SHADING = True
DIVE_SHADE_COLOUR = 'rgba(0,0,0,0.075)'
DEPTH_DOWN_COLOUR = '#ffffff'         # depth line inside the grey bands
DEPTH_UP_COLOUR   = "#bcb9b9"         # depth line inside the white bands
DEPTH_LINE_WIDTH = 1.4
DIVE_MIN_MINUTES = 4        # ignore direction flips shorter than this - noise
                            # and brief inflections, not real phases
DIVE_SMOOTH_N = 9           # samples in the running mean applied to depth
                            # before taking its sign

# ---- 3D tab -------------------------------------------------------------
BATHY_XYZ = None            # None = use the first grid in
                            # data/bathymetry_xyz/. Or a Path to force one.
                            # File is ASCII "lon lat depth" per line, depth
                            # negative downward. No file -> 3D without seabed.
BATHY_STRIDE = 4            # decimate the grid (4 -> every 4th point). Lower
                            # = sharper seabed, much heavier page.
BATHY_PAD_DEG = 0.02        # crop the terrain to the track bbox + this pad.
                            # None = keep the whole file (heavy!).
BATHY_CMAP = 'deep'         # cmocean scale for the seabed
BATHY_CACHE = True          # cache the gridded terrain as .npz next to the
                            # source; delete it after changing BATHY_STRIDE.
SHOW_TERRAIN = True         # False = curtain only, builds much faster
Z_EXAGGERATION = 0.55       # vertical stretch of the 3D scene

N_TIME_WINDOWS = 3          # the deployment is cut into this many chunks and
                            # the slider offers every contiguous RANGE of
                            # them (chunk 2 only, chunks 2-3, and so on).
                            # Steps = N*(N+1)/2, and EACH step stores its own
                            # copy of the curtain geometry:
                            #   3 -> 6 steps, 4 -> 10, 5 -> 15.
                            # This is the main size driver of the 3D tab.

HEIGHT_3D = 860             # px
SCENE_TRANSPARENT = True    # no grey walls behind the 3D scene - the axis
                            # panes become transparent and the page background
                            # shows through.
SCENE_GRID_COLOUR = 'rgba(120,120,120,0.15)'   # faint 3D gridlines; use
                            # 'rgba(0,0,0,0)' to hide them completely.

# ---- map tab ------------------------------------------------------------
# The bathymetry image and its corner coordinates come from
# data/bathymetry_image/ - see config.bathy_image(). Nothing to set here.
BATHY_OPACITY = 0.7
MAP_STYLE = 'carto-positron'   # any style not needing a token, or 'white-bg'
MAP_ZOOM = 9

# ---- depth-averaged currents (map arrows + current rose) ----------------
SHOW_CURRENTS = True        # needs u, v and depth in the timeseries
SURFACE_DEPTH = 15          # m. Shallower than this counts as "at the
                            # surface". Each surfacing splits the record into
                            # intervals; u, v are averaged over each interval,
                            # which is what m_water_vx/vy actually represent -
                            # one estimate per dive, not a time series.
CURRENT_SKIP_FIRST = 10     # drop the first N intervals. Deployment and the
                            # first dives give unreliable depth-averaged
                            # currents.

CURRENT_ARROW_SCALE = 0.10  # DEGREES of latitude drawn per 1 m/s. Purely
                            # visual - raise until the arrows read well at
                            # your usual zoom. The east component is divided
                            # by cos(lat) so the arrow points the true way on
                            # a Mercator basemap.
CURRENT_ARROW_COLOUR = 'red'
CURRENT_ARROW_WIDTH = 2
CURRENT_HEAD_FRAC = 0.25    # arrowhead length as a fraction of the shaft
CURRENT_HEAD_ANGLE = 25     # degrees each barb sits off the shaft
CURRENT_TIP_SIZE = 2        # small marker at the tip - it exists only to
                            # carry the hover text (speed, direction, u/v).
                            # 0 removes it, and the hover with it.

# ---- track styling ------------------------------------------------------
TRACK_VIA_SURFACINGS = True # grey line through the surfacing positions only,
                            # which is where the glider actually got a GPS
                            # fix. False = the full interpolated track.
TRACK_COLOUR = 'lightgrey'
TRACK_WIDTH = 2
SHOW_TRACK_POINTS = False   # every sample as a faint dot as well
SURFACE_MARKER_SIZE = 8
SURFACE_CMAP = 'Viridis'    # surfacings coloured by time order
SHOW_SURFACE_TIMEBAR = True # small colourbar showing what the surfacing
                            # colours mean, dated at both ends
START_END_SIZE = 18

SHOW_CURRENT_ROSE = True    # a "current rose" sub-tab next to the map
ROSE_SECTOR_DEG = 15        # sector width; 15 -> 24 petals

#------ logs form glider tab ------------------------------------------------

SHOW_LOGS = True            # False = no Logs tab at all
LOG_PARQUET_DIR = config.L0_LOGS
                            # L0-logs/<glider>/ - where 03_parse_logs.py
                            # wrote its parquet
 
LOG_TABLE_MAX_ROWS = 400    # newest N dumps in the log book. Every row is
                            # plain HTML, so this is cheap - raise freely.
LOG_ONLY_LAST_DUMP = True   # the glider re-prints the same status every ~60 s
                            # while it sits at the surface. True keeps only
                            # the last dump of each surfacing, which is the
                            # one that actually summarises it. False shows all.
 
# severity colours - deliberately loud, this is the "something changed" signal
LOG_COL_ERROR   = '#ff4d4d'
LOG_COL_WARNING = '#ffb020'
LOG_COL_ODDITY  = '#ffe680'
LOG_COL_OK      = 'transparent'
LOG_COL_ABORT   = '#c026d3'   # magenta: an abort happened on this surfacing

LOG_SHOW_STICKY_ABORT = False
                            # "ABORT HISTORY: last abort ..." is STICKY - the
                            # glider reprints the same last-abort forever, so
                            # it says nothing about the row it appears on.
                            # False shows it only on the surfacing where the
                            # abort actually happened (detected from the abort
                            # timestamp / counter CHANGING). True = old
                            # behaviour, the note on every row.
 
DEVICE_PANEL_MIN_HEIGHT = 210   # px floor per panel
DEVICE_ROW_PX = 15              # px per device row; the panel grows with the
                                # number of devices so the labels stay legible
DEVICE_HIDE_QUIET = False   # True = only show devices that ever logged
                            # something. False keeps every device so a
                            # normally-silent one lighting up is obvious.
 
LOG_SENSOR_HEIGHT = 640
LOG_KEY_SENSORS = ['m_battery', 'm_lithium_battery_relative_charge',
                   'm_coulomb_amphr_total', 'm_vacuum',
                   'm_iridium_signal_strength', 'm_leakdetect_voltage',
                   'm_avg_dive_rate', 'm_avg_climb_rate',
                   'm_tot_num_inflections']
                            # the ones you actually watch every surfacing;
                            # they get their own stacked panel view
LOG_KEY_ROW_HEIGHT = 135
LOG_KEY_BG = '#ececec'      # light grey plot background for the housekeeping
LOG_KEY_GRID = '#ffffff'    # panels, with white gridlines on top of it
LOG_KEY_GRID_WIDTH = 1

#------ battery tab ---------------------------------------------------------

SHOW_BATTERY = True
BATTERY_DIR = config.L0_LOGS      # where 03b_battery.py wrote its JSON

BATT_ROW_HEIGHT = 330             # px per panel (3 panels)
BATT_URGENT_DAYS = 3              # red banner below this many days to recovery
BATT_WARN_DAYS = 7                # amber below this
BATT_MEASURED_COLOUR = "#21c2cb"
BATT_HEADLINE_COLOUR = "#d65e27"
BATT_FAN_COLOUR = 'rgba(120,120,120,0.75)'

# ---- page ---------------------------------------------------------------
OUT_DIR = config.HTML       # <glider>.html is written here


#%% ============================================================
#   setup
#   ============================================================
from pathlib import Path
import base64
import json
import bisect
import datetime as dt

import numpy as np
import xarray as xr
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

OUT_DIR.mkdir(parents=True, exist_ok=True)

try:
    import cmocean.cm as cmo
    HAVE_CMO = True
except ImportError:
    HAVE_CMO = False
    print('tip: `conda install -c conda-forge cmocean` for the ocean colours')


def scale(name, n=32):
    '''plotly colourscale from a cmocean name (falls back to a plotly one).'''
    if HAVE_CMO and hasattr(cmo, name):
        cm = getattr(cmo, name)
        return [[i / (n - 1),
                 'rgb({},{},{})'.format(*(int(255 * c) for c in cm(i / (n - 1))[:3]))]
                for i in range(n)]
    return name if name[0].isupper() else 'Viridis'


def scale_for(var):
    return scale(CMAP_PER_VAR.get(var, 'thermal'))


def stepped(cs, n=N_LEVELS):
    '''continuous colourscale -> n discrete bands'''
    if n is None or n < 2:
        return cs
    if isinstance(cs, str):
        cs = scale(cs)
        if isinstance(cs, str):
            return cs
    pos = [p for p, _ in cs]
    cols = [c for _, c in cs]
    out = []
    for i in range(n):
        f = i / (n - 1)
        j = min(bisect.bisect_left(pos, f), len(cols) - 1)
        out.append([i / n, cols[j]])
        out.append([(i + 1) / n, cols[j]])
    return out


def band_scale(var):
    '''colourscale for the section panels (banded unless SMOOTH_SECTIONS)'''
    cs = scale_for(var)
    return cs if SMOOTH_SECTIONS else stepped(cs)


def clim(a):
    '''(low, high) colour limits from CLIM_PCT percentiles'''
    a = np.asarray(a, float)
    a = a[np.isfinite(a)]
    return (0.0, 1.0) if a.size == 0 else tuple(float(x) for x in
                                                np.percentile(a, CLIM_PCT))


def tsec(times):
    '''datetime64 -> float seconds since epoch'''
    return np.asarray(times, 'datetime64[s]').astype('float64')


def segment_window():
    if SEGMENTS is None:
        return None, None
    seg = SEGMENTS if isinstance(SEGMENTS, (tuple, list)) else (SEGMENTS, None)
    return config.segment_time_range(*seg)


#%% ============================================================
#   data loading
#   ============================================================
def load_grid(glider, t0, t1):
    '''gridded (depth, time) product, optionally with derived salinity'''
    g = xr.open_dataset(config.newest_nc(config.L0_GRID, glider))
    if t0 is not None:
        g = g.sel(time=slice(t0, t1))
    if DERIVE_SALINITY and 'conductivity' in g and 'temperature' in g:
        try:
            import gsw
            C = g['conductivity'].values * 10
            T = g['temperature'].values
            P = np.broadcast_to(g.depth.values[:, None], C.shape)
            lon = float(np.nanmean(g.longitude)) if 'longitude' in g else 0.0
            lat = float(np.nanmean(g.latitude)) if 'latitude' in g else 0.0
            SP = gsw.SP_from_C(C, T, P)
            SA = gsw.SA_from_SP(SP, P, lon, lat)
            CT = gsw.CT_from_t(SA, T, P)
            g['salinity'] = (('depth', 'time'), SP, {'units': 'g/kg'})
            g['potential_density'] = (('depth', 'time'),
                                      gsw.sigma0(SA, CT) + 1000,
                                      {'units': 'kg m-3'})
            print(f'   salinity computed on the grid '
                  f'({int(np.isfinite(SP).sum())} values)')
        except ImportError:
            print('   gsw not installed - no salinity/density')
    return g


def load_ts(glider, t0, t1):
    '''time-series product, thinned to MAX_POINTS'''
    ts = xr.open_dataset(config.newest_nc(config.L0_TS, glider))
    if t0 is not None:
        ts = ts.sel(time=slice(t0, t1))
    n = ts.time.size
    if n > MAX_POINTS:
        step = int(np.ceil(n / MAX_POINTS))
        ts = ts.isel(time=slice(None, None, step))
        print(f'   {n} samples thinned to {ts.time.size} (every {step}th)')
    return ts


#%% ============================================================
#   gridded-field helpers
#   ============================================================
def fill(A, times, max_gap_hours=MAX_GAP_HOURS, max_bins=MAX_FILL_BINS):
    '''Patch small holes: first in the vertical (up to max_bins), then
    between profiles in time - never across a gap longer than
    max_gap_hours.'''
    out = np.array(A, float)
    idx = np.arange(out.shape[0])
    for j in range(out.shape[1]):                       # vertical
        col = out[:, j]
        good = np.isfinite(col)
        if good.sum() < 2:
            continue
        filled = np.interp(idx, idx[good], col[good])
        d = np.abs(idx[:, None] - idx[good][None, :]).min(axis=1)
        out[:, j] = np.where(good | (d <= max_bins), filled, np.nan)
    t = tsec(times)
    gap = max_gap_hours * 3600
    for i in range(out.shape[0]):                       # in time
        row = out[i]
        good = np.isfinite(row)
        if good.sum() < 2:
            continue
        tg = t[good]
        filled = np.interp(t, tg, row[good])
        j = np.searchsorted(tg, t).clip(1, tg.size - 1)
        inside = (t >= tg[0]) & (t <= tg[-1])
        out[i] = np.where(good | (inside & (tg[j] - tg[j - 1] <= gap)),
                          filled, np.nan)
    return out


def uniform_time_axis(times, minutes=REFINE_MINUTES,
                      max_cols=SECTION_MAX_COLS):
    '''Regularly spaced epoch-second axis at ~`minutes` cadence, capped at
    max_cols and never coarser than the real profiles. Regular spacing
    matters: go.Contour misbehaves on an irregular numeric x axis.'''
    t = tsec(times)
    if t.size < 2:
        return t
    n = int((t[-1] - t[0]) / (minutes * 60)) + 1 if minutes else t.size
    n = int(np.clip(n, t.size, max_cols))
    return np.linspace(t[0], t[-1], n)


def interp_to(A, times, tf, max_gap_hours=MAX_GAP_HOURS):
    '''Interpolate each depth row of A onto the epoch-second axis tf.
    Gaps longer than max_gap_hours stay NaN.'''
    t = tsec(times)
    gap = max_gap_hours * 3600.0
    out = np.full((A.shape[0], tf.size), np.nan)
    for i in range(A.shape[0]):
        row = A[i]
        good = np.isfinite(row)
        if good.sum() < 2:
            continue
        tg = t[good]
        vals = np.interp(tf, tg, row[good])
        j = np.searchsorted(tg, tf).clip(1, tg.size - 1)
        inside = (tf >= tg[0]) & (tf <= tg[-1])
        out[i] = np.where(inside & (tg[j] - tg[j - 1] <= gap), vals, np.nan)
    return out


def crop_empty_rows(Z, depths):
    '''drop depth bins that are NaN everywhere (the deep staircase)'''
    keep = np.isfinite(Z).any(axis=1)
    return (Z[keep], depths[keep]) if keep.any() else (Z, depths)


def profile_lines(A, times, depths, every=PROFILE_LINE_EVERY):
    '''One trace: a dashed vertical line at each real profile, surface ->
    deepest bin with data. x is datetime64, matching the contour axis.
    go.Scatter (not Scattergl) because only SVG renders dashes reliably.'''
    xs, ys = [], []
    for j in range(0, A.shape[1], every):
        good = np.isfinite(A[:, j])
        if not good.any():
            continue
        dmax = depths[np.where(good)[0][-1]]
        xs += [times[j], times[j], None]
        ys += [depths[0], dmax, None]
    if not xs:
        return None
    return go.Scatter(x=xs, y=ys, mode='lines',
                      line=dict(width=PROFILE_LINE_WIDTH,
                                color=PROFILE_LINE_COLOUR,
                                dash=PROFILE_LINE_DASH),
                      connectgaps=False,
                      hoverinfo='skip', showlegend=False)


#%% ============================================================
#   TAB 1 - sections (go.Contour on a uniform datetime64 axis)
#   ============================================================
def sections_fig(grid):
    have = [v for v in SECTION_VARS if v in grid]
    if not have:
        return None

    times = grid.time.values
    tf = uniform_time_axis(times)
    xdt = tf.astype('datetime64[s]')      # datetime64, NOT epoch floats:
                                          # numeric x + NaN gaps breaks Contour
    print(f'   sections: {len(have)} panels, {tf.size} columns')

    fig = make_subplots(rows=len(have), cols=1, shared_xaxes=False,
                        vertical_spacing=0.055,
                        subplot_titles=[f"{v} [{grid[v].attrs.get('units','')}]"
                                        for v in have])

    for k, v in enumerate(have):
        A = grid[v].values
        if FILL_GAPS:
            A = fill(A, times)
        lo, hi = clim(A)
        Z = interp_to(A, times, tf)
        Z, depths = crop_empty_rows(Z, grid.depth.values)
        if SECTION_DEPTH_STRIDE > 1:
            Z = Z[::SECTION_DEPTH_STRIDE]
            depths = depths[::SECTION_DEPTH_STRIDE]
        Z = np.round(Z, SECTION_DECIMALS.get(v, SECTION_DECIMALS_DEFAULT))
        cs = band_scale(v)
        bar = dict(len=1 / len(have) - 0.03, thickness=11,
                   y=1 - (k + 0.5) / len(have))

        if not np.isfinite([lo, hi]).all() or hi - lo < MIN_LEVEL_SPAN:
            # constant or empty field -> contours would be blank
            print(f'   {v}: constant or empty, using a heatmap')
            fig.add_trace(go.Heatmap(
                z=Z, x=xdt, y=depths, colorscale=cs, zmin=lo, zmax=hi,
                colorbar=bar,
                hovertemplate='%{x|%d %b %H:%M}<br>%{y:.0f} m<br>'
                              '%{z:.3f}<extra></extra>'),
                row=k + 1, col=1)
        else:
            fig.add_trace(go.Contour(
                z=Z, x=xdt, y=depths,
                colorscale=cs, zmin=lo, zmax=hi,
                contours=dict(start=lo, end=hi, size=(hi - lo) / N_LEVELS,
                              coloring='fill', showlines=SHOW_CONTOUR_LINES,
                              showlabels=CONTOUR_LABELS),
                line=dict(width=CONTOUR_LINE_WIDTH if SHOW_CONTOUR_LINES else 0,
                          color=CONTOUR_LINE_COLOUR,
                          smoothing=CONTOUR_LINE_SMOOTHING),
                connectgaps=False, colorbar=bar,
                hovertemplate='%{x|%d %b %H:%M}<br>%{y:.0f} m<br>'
                              '%{z:.3f}<extra></extra>'),
                row=k + 1, col=1)

        if SHOW_PROFILE_LINES:
            tr = profile_lines(A, times, grid.depth.values)
            if tr is not None:
                fig.add_trace(tr, row=k + 1, col=1)

        fig.update_yaxes(autorange='reversed', title_text='depth [m]',
                         row=k + 1, col=1)
        fig.update_xaxes(showticklabels=True, row=k + 1, col=1)

    fig.update_layout(
        height=SECTION_ROW_HEIGHT * len(have) + 80,
        template='plotly_white', dragmode='zoom',
        margin=dict(t=60, l=65, r=20, b=45))
    return fig


#%% ============================================================
#   TAB 2 - Science scatter
#   ============================================================
def column(ts, name):
    if name == 'time':
        return [str(t)[:19] for t in ts.time.values]
    v = np.asarray(ts[name].values, float)
    return [None if not np.isfinite(x) else round(float(x), 6) for x in v]


def scatter_fig(ts, varlist, default, title):
    '''Scatter with three dropdowns: x, y, and which variable colours the
    markers. The colourmap follows from CMAP_PER_VAR, so there is no separate
    "scheme" control to keep in sync.'''
    have = [v for v in varlist if v == 'time' or v in ts]
    if not have:
        return None
    cols = {v: column(ts, v) for v in have}
    xd = default[0] if default[0] in have else have[0]
    yd = default[1] if default[1] in have else have[-1]
    cd = next((v for v in ('temperature', 'depth') if v in have), have[0])
    num = lambda v: [np.nan if q is None else q for q in cols[v]]

    fig = go.Figure(go.Scattergl(
        x=cols[xd], y=cols[yd], mode='markers',
        marker=dict(size=MARKER_SIZE, color=num(cd), colorscale=scale_for(cd),
                    showscale=True, opacity=0.9,
                    line=dict(width=MARKER_OUTLINE_WIDTH,
                              color=MARKER_OUTLINE_COLOUR),
                    colorbar=dict(title=cd, thickness=12)),
        hovertemplate='%{x}<br>%{y}<extra></extra>', showlegend=False))

    def menu(kind, active, x):
        b = []
        for v in have:
            if kind == 'x':
                args = [{'x': [cols[v]]}, {'xaxis.title.text': v}]
            elif kind == 'y':
                args = [{'y': [cols[v]]},
                        {'yaxis.title.text': v,
                         'yaxis.autorange': 'reversed' if v == 'depth' else True}]
            else:
                args = [{'marker.color': [num(v)],
                         'marker.colorscale': [scale_for(v)],
                         'marker.colorbar.title.text': v}, {}]
            b.append(dict(label=v, method='update', args=args))
        return dict(buttons=b, direction='down', showactive=True, x=x,
                    xanchor='left', y=1.10, yanchor='top',
                    active=have.index(active))

    fig.update_layout(
        updatemenus=[menu('x', xd, 0.0), menu('y', yd, 0.22),
                     menu('c', cd, 0.44)],
        annotations=[dict(text=t, x=p, y=1.12, xref='paper', yref='paper',
                          showarrow=False, xanchor='right')
                     for t, p in (('x', -0.005), ('y', 0.215),
                                  ('colour', 0.435))],
        height=SCIENCE_HEIGHT, template='plotly_white',
        plot_bgcolor=SCATTER_BG,
        margin=dict(t=95, l=60, r=20, b=50), title='')
        
    fig.update_xaxes(title_text=xd)
    fig.update_yaxes(title_text=yd)
    if yd == 'depth':
        fig.update_yaxes(autorange='reversed')
    return fig


#%% ============================================================
#   T-S diagram
#   ============================================================
def ts_fig(ts):
    '''Salinity on x, temperature on y, potential density as isolines.

    Markers get a thin dark ring: the depth colourmap starts near white, so
    without it the shallowest points disappear into the page. The sigma0
    legend entry sits above the plot so it cannot land on the colourbar.
    '''
    if 'salinity' not in ts or 'temperature' not in ts:
        print('   no salinity/temperature - skipping the T-S diagram')
        return None
    S = np.asarray(ts['salinity'].values, float)
    T = np.asarray(ts['temperature'].values, float)
    ok = np.isfinite(S) & np.isfinite(T)
    if ok.sum() < 10:
        return None
    S, T = S[ok], T[ok]

    fig = go.Figure()

    if TS_DENSITY_CONTOURS:
        try:
            import gsw
            sg = np.linspace(S.min() - 0.05, S.max() + 0.05, 120)
            tg = np.linspace(T.min() - 0.3, T.max() + 0.3, 120)
            SS, TT = np.meshgrid(sg, tg)
            SA = gsw.SA_from_SP(SS, 0,
                                float(np.nanmean(ts['longitude']))
                                if 'longitude' in ts else 0.0,
                                float(np.nanmean(ts['latitude']))
                                if 'latitude' in ts else 0.0)
            CT = gsw.CT_from_t(SA, TT, 0)
            SIG = gsw.sigma0(SA, CT)
            lo, hi = float(np.nanmin(SIG)), float(np.nanmax(SIG))
            fig.add_trace(go.Contour(
                z=SIG, x=sg, y=tg,
                contours=dict(start=lo, end=hi,
                              size=max((hi - lo) / TS_N_DENSITY_LINES, 1e-6),
                              coloring='none', showlines=True, showlabels=True,
                              labelfont=dict(size=10, color='rgba(0,0,0,0.6)')),
                line=dict(width=0.7, color='rgba(0,0,0,0.45)'),
                showscale=False, hoverinfo='skip', name='sigma0',
                showlegend=True))
        except ImportError:
            print('   gsw not installed - T-S without density contours')

    cvar = TS_COLOUR_BY if TS_COLOUR_BY in ts else 'depth'
    C = np.asarray(ts[cvar].values, float)[ok] if cvar in ts else None
    fig.add_trace(go.Scattergl(
        x=S, y=T, mode='markers',
        marker=dict(size=MARKER_SIZE, opacity=0.9,
                    line=dict(width=MARKER_OUTLINE_WIDTH,
                              color=MARKER_OUTLINE_COLOUR),
                    color=C if C is not None else 'steelblue',
                    colorscale=scale_for(cvar) if C is not None else None,
                    showscale=C is not None,
                    colorbar=dict(title=cvar, thickness=12,
                                  len=0.82, y=0.42, yanchor='middle')),
        hovertemplate='S %{x:.3f}<br>T %{y:.3f}<extra></extra>',
        showlegend=False))

    fig.update_layout(
        xaxis_title='salinity', yaxis_title='temperature [degC]',
        height=TS_HEIGHT, template='plotly_white',
        plot_bgcolor=SCATTER_BG,
        margin=dict(t=95, l=60, r=20, b=50),
        legend=dict(orientation='h', y=1.06, yanchor='bottom',
                    x=1, xanchor='right', font=dict(size=11)),
        title='T-S diagram (thin lines = potential density sigma0)')
    return fig


#%% ============================================================
#   TAB 3 - Glider: engineering variables stacked against time
#   ============================================================
def dive_phases(ts, min_minutes=DIVE_MIN_MINUTES, smooth_n=DIVE_SMOOTH_N):
    '''-> [(t0, t1, 'down'|'up')] from the sign of d(depth)/dt.

    Depth is smoothed first, then runs shorter than min_minutes are absorbed
    into the run before them, so a moment of level flight mid-descent does
    not chop the shading into slivers.'''
    if 'depth' not in ts:
        return []
    d = np.asarray(ts.depth.values, float)
    t = np.asarray(ts.time.values)
    ok = np.isfinite(d)
    if ok.sum() < 3:
        return []
    d, t = d[ok], t[ok]

    if smooth_n > 1 and d.size > smooth_n:
        d = np.convolve(d, np.ones(smooth_n) / smooth_n, mode='same')

    s = np.sign(np.diff(d))
    nz = s != 0
    if not nz.any():
        return []
    carry = np.where(nz, np.arange(s.size), 0)   # forward-fill the zeros
    np.maximum.accumulate(carry, out=carry)
    s = s[carry]

    cuts = np.where(np.diff(s) != 0)[0] + 1
    runs = list(zip(np.r_[0, cuts], np.r_[cuts, s.size]))

    merged = []
    for a, b in runs:
        mins = (t[min(b, t.size - 1)] - t[a]) / np.timedelta64(1, 'm')
        if mins < min_minutes and merged:
            merged[-1][1] = b                    # too short: absorb it
        else:
            merged.append([a, b, s[a]])
    out = []                                     # join same-direction runs
    for a, b, sign in merged:
        if out and out[-1][2] == sign:
            out[-1][1] = b
        else:
            out.append([a, b, sign])

    return [(t[a], t[min(b, t.size - 1)], 'down' if sign > 0 else 'up')
            for a, b, sign in out]


def _nz(a, dec=3):
    '''numpy array -> JSON-friendly list, NaN as None, rounded'''
    a = np.asarray(a, float)
    return [None if not np.isfinite(x) else round(float(x), dec) for x in a]


def glider_fig(ts):
    '''Engineering variables stacked against time, one short panel each,
    all sharing the zoom - so an unusual moment is visible in a glance
    rather than found by clicking through a dropdown.

    Per panel: commanded is drawn first and measured second, so measured is
    always the trace on top. The depth panel at the top splits the dive into
    phases - grey band with a white line while descending, white band with a
    grey line while ascending - and every panel carries the same bands.
    '''
    if 'depth' not in ts:
        print('   no depth - skipping the Glider tab')
        return None

    groups = [(v, GLIDER_PAIR_PREFIX + v
               if GLIDER_PAIR_PREFIX + v in ts else None)
              for v in GLIDER_Y_VARS if v in ts]
    if not groups:
        print('   no engineering variables - skipping the Glider tab')
        return None

    t = np.asarray(ts.time.values)
    phases = dive_phases(ts)
    n_down = sum(1 for *_, d in phases if d == 'down')
    print(f'   glider: {len(groups)} panels, {len(phases)} dive phases '
          f'({n_down} descending)')

    rows = len(groups) + 1
    heights = [GLIDER_DEPTH_ROW_HEIGHT] + [GLIDER_ROW_HEIGHT] * len(groups)
    total = sum(heights)
    titles = ['depth [m]'] + [
        f"{v} [{ts[v].attrs.get('units', '')}]" +
        ('   (dark = commanded)' if cmd else '')
        for v, cmd in groups]

    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True,
                        vertical_spacing=min(0.02, 0.8 / max(rows - 1, 1)),
                        row_heights=[h / total for h in heights],
                        subplot_titles=titles)

    # ---- depth panel: the line changes colour with the dive phase --------
    d = np.asarray(ts.depth.values, float)
    down = np.full(d.size, np.nan)
    up = np.full(d.size, np.nan)
    for a, b, direction in phases:
        m = (t >= a) & (t <= b)
        if direction == 'down':
            down[m] = d[m]
        else:
            up[m] = d[m]
    if not phases:                       # no phases found: draw it plainly
        up = d

    for arr, colour, label in ((up, DEPTH_UP_COLOUR, 'ascending'),
                               (down, DEPTH_DOWN_COLOUR, 'descending')):
        fig.add_trace(go.Scattergl(
            x=t, y=_nz(arr, 2), mode='lines',
            line=dict(width=DEPTH_LINE_WIDTH, color=colour),
            name=label, showlegend=False, connectgaps=False,
            hovertemplate='%{x|%d %b %H:%M}<br>%{y:.1f} m'
                          f'<extra>{label}</extra>'),
            row=1, col=1)

    # ---- one panel per variable -----------------------------------------
    for k, (v, cmd) in enumerate(groups):
        r = k + 2
        first = (k == 0)                 # legend entries only once

        if cmd:                          # commanded FIRST -> drawn underneath
            fig.add_trace(go.Scattergl(
                x=t, y=_nz(ts[cmd].values), mode='lines',
                line=dict(width=GLIDER_LINE_WIDTH,
                          color=GLIDER_COMMANDED_COLOUR),
                name='commanded', legendgroup='commanded',
                showlegend=first,
                hovertemplate='%{x|%d %b %H:%M}<br>%{y}'
                              f'<extra>{cmd}</extra>'), row=r, col=1)

        fig.add_trace(go.Scattergl(
            x=t, y=_nz(ts[v].values),
            mode='lines+markers' if GLIDER_MARKER_SIZE else 'lines',
            line=dict(width=GLIDER_LINE_WIDTH,
                      color=GLIDER_MEASURED_COLOUR),
            marker=dict(size=GLIDER_MARKER_SIZE,
                        color=GLIDER_MEASURED_COLOUR),
            name='measured', legendgroup='measured', showlegend=first,
            hovertemplate='%{x|%d %b %H:%M}<br>%{y}'
                          f'<extra>{v}</extra>'), row=r, col=1)

        fig.update_yaxes(title_text='', row=r, col=1)

    # ---- dive shading on every panel ------------------------------------
    # x0/x1 must be ISO STRINGS: numpy datetime64 in a layout shape does not
    # survive serialisation.
    if SHOW_DIVE_SHADING:
        for a, b, direction in phases:
            if direction != 'down':
                continue                 # ascents are the page background
            x0 = np.datetime_as_string(a, unit='s')
            x1 = np.datetime_as_string(b, unit='s')
            for r in range(1, rows + 1):
                fig.add_shape(type='rect', x0=x0, x1=x1, y0=0, y1=1,
                              yref='y domain', fillcolor=DIVE_SHADE_COLOUR,
                              line_width=0, layer='below', row=r, col=1)

    fig.update_yaxes(autorange='reversed', title_text='depth [m]',
                     row=1, col=1)
    fig.update_xaxes(title_text='time', row=rows, col=1)
    for ann in fig.layout.annotations:   # subplot titles, left-aligned
        ann.update(x=0, xanchor='left', font=dict(size=12.5))

    fig.update_layout(
        height=total + 130, template='plotly_white',
        margin=dict(t=90, l=65, r=20, b=45),
        legend=dict(orientation='h', y=1.035, x=0, xanchor='left'),
        hovermode='x unified', dragmode='zoom',
        title='Orange = measured, dark = commanded | '
              'grey bands = descending, white = ascending')
    return fig


#%% ============================================================
#   bathymetry terrain
#   ============================================================
def load_bathy_terrain(path=BATHY_XYZ, stride=BATHY_STRIDE,
                       bbox=None, pad=BATHY_PAD_DEG):
    '''Read an ASCII "lon lat depth" grid and reshape it to a regular 2D
    array. path=None -> whatever is in data/bathymetry_xyz/. Cached as .npz
    next to the source.'''
    path = Path(path) if path else config.find_bathy_xyz()
    if path is None or not path.exists():
        return None
    cache = path.with_suffix(f'.grid{stride}.npz')
    if BATHY_CACHE and cache.exists():
        d = np.load(cache)
        lon, lat, Z = d['lon'], d['lat'], d['Z']
        print(f'   terrain from cache {cache.name}  {Z.shape}')
    else:
        try:
            import pandas as pd
            xyz = pd.read_csv(path, sep=r'\s+', header=None,
                              names=['lon', 'lat', 'z'], comment='#').values
        except ImportError:
            xyz = np.loadtxt(path)
        lon = np.unique(xyz[:, 0])
        lat = np.unique(xyz[:, 1])
        Z = np.full((lat.size, lon.size), np.nan)
        ix = np.searchsorted(lon, xyz[:, 0])
        iy = np.searchsorted(lat, xyz[:, 1])
        Z[iy, ix] = xyz[:, 2]
        if stride and stride > 1:
            lon, lat, Z = lon[::stride], lat[::stride], Z[::stride, ::stride]
        print(f'   terrain gridded {Z.shape} '
              f'({lon[0]:.3f}..{lon[-1]:.3f}, {lat[0]:.3f}..{lat[-1]:.3f})')
        if BATHY_CACHE:
            np.savez_compressed(cache, lon=lon, lat=lat, Z=Z)
    if bbox is not None and pad is not None:
        w, e, s, n = bbox
        mx = (lon >= w - pad) & (lon <= e + pad)
        my = (lat >= s - pad) & (lat <= n + pad)
        if mx.sum() > 4 and my.sum() > 4:
            lon, lat, Z = lon[mx], lat[my], Z[np.ix_(my, mx)]
            print(f'   terrain cropped to the track -> {Z.shape}')
    return lon, lat, Z


def scene_axes():
    '''3D axis styling: transparent panes so no grey walls sit behind the
    terrain, and very faint gridlines.'''
    if not SCENE_TRANSPARENT:
        return {}
    a = dict(showbackground=False, backgroundcolor='rgba(0,0,0,0)',
             gridcolor=SCENE_GRID_COLOUR, zerolinecolor=SCENE_GRID_COLOUR,
             showspikes=False)
    return dict(xaxis=dict(a), yaxis=dict(a), zaxis=dict(a))


def terrain_trace(terrain):
    lon, lat, Z = terrain
    X, Y = np.meshgrid(lon, lat)
    return go.Surface(
        x=X, y=Y, z=Z, surfacecolor=Z, colorscale=scale(BATHY_CMAP),
        showscale=False, opacity=1.0, name='bathymetry',
        lighting=dict(ambient=0.65, diffuse=0.8, specular=0.15, roughness=0.9),
        contours=dict(z=dict(show=False)),
        hovertemplate='%{x:.4f}, %{y:.4f}<br>%{z:.0f} m<extra>seabed</extra>')


#%% ============================================================
#   TAB 4 - 3D curtain over the terrain
#   ============================================================
def curtain_arrays(grid, have):
    lon = np.asarray(grid.longitude.values, float)
    lat = np.asarray(grid.latitude.values, float)
    ok = np.isfinite(lon) & np.isfinite(lat)
    i = np.arange(lon.size)
    lon = np.interp(i, i[ok], lon[ok])
    lat = np.interp(i, i[ok], lat[ok])
    z = grid.depth.values
    fields = {v: (fill(grid[v].values, grid.time.values) if FILL_GAPS
                  else np.array(grid[v].values, float)) for v in have}
    return lon, lat, z, fields


def masked_curtain(lon, lat, z, F, keep):
    '''Curtain geometry for the columns in `keep`. Z is NaN wherever the
    field is NaN, so unmeasured parts render transparent instead of as a
    grey wall.'''
    lo, la, f = lon[keep], lat[keep], F[:, keep]
    X = np.broadcast_to(lo, (z.size, lo.size)).astype(float).copy()
    Y = np.broadcast_to(la, (z.size, la.size)).astype(float).copy()
    Z = np.broadcast_to(-z[:, None], X.shape).astype(float).copy()
    Z[~np.isfinite(f)] = np.nan
    return X, Y, Z, f


def _stamp(x):
    return dt.datetime.utcfromtimestamp(float(x)).strftime('%d %b %H:%M')


def time_ranges(t, n=N_TIME_WINDOWS):
    '''Every contiguous RANGE of n equal time chunks, as (label, mask).

    A slider step in plotly carries one fixed set of arrays, so a genuine
    from-to control means precomputing each range. That is n(n+1)/2 steps,
    each holding its own copy of the curtain - which is why N_TIME_WINDOWS
    stays small.
    '''
    edges = np.linspace(t[0], t[-1], n + 1)
    out = [('whole period', np.ones(t.size, bool))]
    for i in range(n):
        for j in range(i, n):
            if i == 0 and j == n - 1:
                continue                        # that is 'whole period'
            keep = (t >= edges[i]) & (t <= edges[j + 1])
            if keep.sum() < 2:
                continue
            label = (f'{i + 1}' if i == j else f'{i + 1}-{j + 1}') + \
                    f'   {_stamp(edges[i])} -> {_stamp(edges[j + 1])}'
            out.append((label, keep))
    return out


def curtain_fig(grid, ts, terrain):
    have = [v for v in SECTION_VARS if v in grid]
    if 'longitude' not in grid or 'latitude' not in grid or not have:
        print('   no position on the grid - 3D falls back to points')
        return scatter3d_fig(ts, terrain)
    lon, lat, z, fields = curtain_arrays(grid, have)
    t = tsec(grid.time.values)

    windows = time_ranges(t)
    print(f'   3D: {len(windows)} time ranges from {N_TIME_WINDOWS} chunks')

    first = have[0]
    fig = go.Figure()

    ti = None
    if SHOW_TERRAIN and terrain is not None:
        fig.add_trace(terrain_trace(terrain))
        ti = 0
    cur_i = len(fig.data)                       # index of the curtain trace

    X, Y, Z, F = masked_curtain(lon, lat, z, fields[first], windows[0][1])
    lo, hi = clim(fields[first])
    fig.add_trace(go.Surface(
        x=X, y=Y, z=Z, surfacecolor=F, colorscale=stepped(scale_for(first)),
        cmin=lo, cmax=hi, name=first, showscale=True,
        colorbar=dict(title=first, thickness=12, len=0.7),
        hovertemplate='%{x:.4f}, %{y:.4f}<br>%{z:.0f} m<br>'
                      '%{surfacecolor:.3f}<extra></extra>'))

    # switching variable resets the view to the whole period
    var_buttons = []
    for v in have:
        vlo, vhi = clim(fields[v])
        _, _, Zv, Fv = masked_curtain(lon, lat, z, fields[v], windows[0][1])
        var_buttons.append(dict(
            label=v, method='restyle',
            args=[{'z': [Zv], 'surfacecolor': [Fv],
                   'colorscale': [stepped(scale_for(v))],
                   'cmin': vlo, 'cmax': vhi,
                   'colorbar.title.text': v}, [cur_i]]))

    steps = []
    for lbl, keep in windows:
        Xw, Yw, Zw, Fw = masked_curtain(lon, lat, z, fields[first], keep)
        steps.append(dict(label=lbl, method='restyle',
                          args=[{'x': [Xw], 'y': [Yw], 'z': [Zw],
                                 'surfacecolor': [Fw]}, [cur_i]]))

    menus = [dict(buttons=var_buttons, direction='down', showactive=True,
                  x=0, xanchor='left', y=1.0, yanchor='top')]
    if ti is not None:
        menus.append(dict(buttons=[
            dict(label='terrain on', method='restyle',
                 args=[{'visible': [True]}, [ti]]),
            dict(label='terrain off', method='restyle',
                 args=[{'visible': [False]}, [ti]])],
            direction='down', showactive=True,
            x=0.24, xanchor='left', y=1.0, yanchor='top'))

    fig.update_layout(
        updatemenus=menus,
        sliders=[dict(active=0, currentvalue=dict(prefix='period: ',
                                                  font=dict(size=12)),
                      pad=dict(t=30, b=10), steps=steps,
                      x=0.02, len=0.96, y=-0.02, yanchor='top')],
        annotations=[dict(text='variable', x=-0.005, y=1.005, xref='paper',
                          yref='paper', showarrow=False, xanchor='right')],
        scene=dict(xaxis_title='longitude', yaxis_title='latitude',
                   zaxis_title='depth [m]', aspectmode='manual',
                   aspectratio=dict(x=1, y=1, z=Z_EXAGGERATION),
                   camera=dict(eye=dict(x=1.4, y=-1.4, z=0.8)),
                   **scene_axes()),
        paper_bgcolor='rgba(0,0,0,0)' if SCENE_TRANSPARENT else None,
        height=HEIGHT_3D, margin=dict(t=50, l=0, r=0, b=120),
        title=dict(text='Seabed + measured variables',
                   yref='container', y=0.985, yanchor='top',
                   x=0.5, xanchor='center'))
    return fig


def scatter3d_fig(ts, terrain=None):
    '''fallback when the grid has no position: coloured points on the track'''
    need = {'longitude', 'latitude', 'depth'}
    if not need <= set(ts.data_vars) | set(ts.coords):
        return None
    opts = [v for v in SCIENCE_VARS if v in ts and v not in
            ('time', 'longitude', 'latitude')]
    first = opts[0] if opts else 'depth'
    num = lambda v: [np.nan if q is None else q for q in column(ts, v)]
    lo, hi = clim(num(first))
    fig = go.Figure()
    if SHOW_TERRAIN and terrain is not None:
        fig.add_trace(terrain_trace(terrain))
    fig.add_trace(go.Scatter3d(
        x=column(ts, 'longitude'), y=column(ts, 'latitude'),
        z=[None if q is None else -q for q in column(ts, 'depth')],
        mode='markers',
        marker=dict(size=MARKER_SIZE_3D, color=num(first),
                    colorscale=scale_for(first), cmin=lo, cmax=hi,
                    opacity=0.9, line=dict(width=0),
                    colorbar=dict(title=first, thickness=12))))
    ci = len(fig.data) - 1
    fig.update_layout(
        updatemenus=[dict(buttons=[
            dict(label=v, method='restyle',
                 args=[{'marker.color': [num(v)],
                        'marker.colorscale': [scale_for(v)],
                        'marker.cmin': clim(num(v))[0],
                        'marker.cmax': clim(num(v))[1],
                        'marker.colorbar.title.text': v}, [ci]])
            for v in opts], direction='down', showactive=True,
            x=0, xanchor='left', y=1.0, yanchor='top')],
        scene=dict(xaxis_title='longitude', yaxis_title='latitude',
                   zaxis_title='depth [m]', aspectmode='manual',
                   aspectratio=dict(x=1, y=1, z=Z_EXAGGERATION),
                   **scene_axes()),
        paper_bgcolor='rgba(0,0,0,0)' if SCENE_TRANSPARENT else None,
        height=HEIGHT_3D, margin=dict(t=110, l=0, r=0, b=10),
        title=dict(text='3D track', yref='container', y=0.985,
                   yanchor='top', x=0.5, xanchor='center'))
    return fig


#%% ============================================================
#   TAB 5 - map + average currents
#   ============================================================
def bathy_layer():
    '''Georeferenced image layer for the map, from data/bathymetry_image/.
    The image is base64-embedded in the page, so its file size is added to
    every glider's html - keep it well under 2 MB.'''
    p, bounds = config.bathy_image()
    if p is None:
        return None
    s, w, n, e = bounds
    uri = (f'data:image/{p.suffix.lstrip(".").lower()};base64,'
           + base64.b64encode(p.read_bytes()).decode())
    print(f'   bathymetry: {p.name} ({p.stat().st_size/1e6:.1f} MB)')
    return dict(sourcetype='image', source=uri, below='traces',
                opacity=BATHY_OPACITY,
                coordinates=[[w, n], [e, n], [e, s], [w, s]])


def surface_intervals(ts, surface_depth=SURFACE_DEPTH,
                      skip=CURRENT_SKIP_FIRST):
    '''Split the record at surfacings and average u, v over each interval.

    m_water_vx/vy is a depth-averaged estimate the glider computes per dive,
    so one vector per surface-to-surface interval is the honest sampling -
    plotting it per sample would repeat the same number hundreds of times.

    Returns a dict of arrays (lon, lat mid-interval; lon0/lat0, lon1/lat1 the
    endpoints; u, v, speed, direction, t0, t1) or None.
    '''
    need = {'u', 'v'}
    if not need <= set(ts.data_vars) or 'depth' not in ts:
        print('   no u/v/depth - no current vectors')
        return None

    depth = np.asarray(ts.depth.values, float)
    idx = np.where(depth < surface_depth)[0]
    if idx.size < 3:
        print('   no surfacings found - no current vectors')
        return None

    breaks = np.where(np.diff(idx) > 1)[0]
    ev = idx[np.r_[0, breaks + 1]]          # first sample of each surfacing
    print(f'   {ev.size} surface events '
          f'(depth < {surface_depth} m), skipping the first {skip}')
    if ev.size - 1 <= skip:
        print('   not enough intervals left after the skip')
        return None

    lon = np.asarray(ts.longitude.values, float)
    lat = np.asarray(ts.latitude.values, float)
    u = np.asarray(ts.u.values, float)
    v = np.asarray(ts.v.values, float)
    t = np.asarray(ts.time.values)

    r = dict(lon0=[], lat0=[], lon1=[], lat1=[], lon=[], lat=[],
             u=[], v=[], t0=[], t1=[])
    for a, b in zip(ev[skip:-1], ev[skip + 1:]):
        seg_u, seg_v = u[a:b], v[a:b]
        if not (np.isfinite(seg_u).any() and np.isfinite(seg_v).any()):
            continue
        if not (np.isfinite(lon[[a, b]]).all()
                and np.isfinite(lat[[a, b]]).all()):
            continue
        r['lon0'].append(lon[a]);  r['lat0'].append(lat[a])
        r['lon1'].append(lon[b]);  r['lat1'].append(lat[b])
        r['lon'].append((lon[a] + lon[b]) / 2)
        r['lat'].append((lat[a] + lat[b]) / 2)
        r['u'].append(np.nanmean(seg_u))
        r['v'].append(np.nanmean(seg_v))
        r['t0'].append(t[a]);      r['t1'].append(t[b])

    if not r['u']:
        print('   every interval was NaN - no current vectors')
        return None

    for k in ('lon0', 'lat0', 'lon1', 'lat1', 'lon', 'lat', 'u', 'v'):
        r[k] = np.asarray(r[k], float)
    r['speed'] = np.hypot(r['u'], r['v'])
    # compass bearing the current flows TOWARD (0 = north, 90 = east)
    r['direction'] = (np.degrees(np.arctan2(r['u'], r['v'])) + 360) % 360
    print(f'   {r["u"].size} current vectors, '
          f'{np.nanmin(r["speed"]):.3f}-{np.nanmax(r["speed"]):.3f} m/s')
    return r


def current_arrows(cur, deg_per_ms=CURRENT_ARROW_SCALE,
                   head_frac=CURRENT_HEAD_FRAC, head_deg=CURRENT_HEAD_ANGLE):
    '''Arrows with heads, all in ONE trace using None breaks.

    Scattermap has no arrowhead, so each head is two short barbs rotated back
    from the tip. Geometry is done in a local east-metric space (dlon scaled
    by cos(lat)) and converted back, otherwise the heads are skewed and the
    shafts point slightly wrong on a Mercator basemap.'''
    coslat = np.cos(np.radians(cur['lat']))
    ex = cur['u'] * deg_per_ms            # east component, metric-ish
    ey = cur['v'] * deg_per_ms            # north component
    lon1 = cur['lon'] + ex / coslat
    lat1 = cur['lat'] + ey

    mag = np.hypot(ex, ey)
    mag[mag == 0] = np.nan                # zero-length arrow gets no head
    ux, uy = -ex / mag, -ey / mag         # unit vector pointing back down it

    a = np.radians(head_deg)
    ca, sa = np.cos(a), np.sin(a)
    barbs = []
    for s in (+1, -1):                    # rotate the back-vector both ways
        rx = ux * ca - uy * (s * sa)
        ry = ux * (s * sa) + uy * ca
        blon = lon1 + rx * mag * head_frac / coslat
        blat = lat1 + ry * mag * head_frac
        barbs.append((blon, blat))

    xs, ys = [], []
    for i in range(cur['lon'].size):
        xs += [cur['lon'][i], lon1[i], None]          # shaft
        ys += [cur['lat'][i], lat1[i], None]
        for blon, blat in barbs:                      # two barbs
            if np.isfinite(blon[i]) and np.isfinite(blat[i]):
                xs += [lon1[i], blon[i], None]
                ys += [lat1[i], blat[i], None]

    shafts = go.Scattermap(
        lon=xs, lat=ys, mode='lines',
        line=dict(width=CURRENT_ARROW_WIDTH, color=CURRENT_ARROW_COLOUR),
        name='depth-avg current', hoverinfo='skip')

    out = [shafts]
    if CURRENT_TIP_SIZE:
        out.append(go.Scattermap(
            lon=lon1, lat=lat1, mode='markers',
            marker=dict(size=CURRENT_TIP_SIZE, color=CURRENT_ARROW_COLOUR),
            name='current', showlegend=False,
            text=[f'{str(a_):.16s} -> {str(b_):.16s}<br>'
                  f'{s_:.3f} m/s toward {d_:.0f} deg<br>'
                  f'u {uu:+.3f}, v {vv:+.3f}'
                  for a_, b_, s_, d_, uu, vv in
                  zip(cur['t0'], cur['t1'], cur['speed'], cur['direction'],
                      cur['u'], cur['v'])],
            hovertemplate='%{text}<extra></extra>'))
    return out


def map_fig(ts, bathy):
    '''Basemap + bathymetry image + track through the surfacings, coloured by
    time + depth-averaged current arrows.'''
    if not {'longitude', 'latitude'} <= set(ts.data_vars) | set(ts.coords):
        print('   no position - skipping the map')
        return None
    lon = np.asarray(ts['longitude'].values, float)
    lat = np.asarray(ts['latitude'].values, float)
    ok = np.isfinite(lon) & np.isfinite(lat)
    if ok.sum() == 0:
        print('   position is all NaN - skipping the map')
        return None
    lon, lat, times = lon[ok], lat[ok], np.asarray(ts.time.values)[ok]

    cur = surface_intervals(ts) if SHOW_CURRENTS else None

    # the grey line follows the surfacings (real GPS fixes) when we have them
    if TRACK_VIA_SURFACINGS and cur is not None:
        tlon = np.append(cur['lon0'], cur['lon1'][-1])
        tlat = np.append(cur['lat0'], cur['lat1'][-1])
        ttime = np.append(cur['t0'], cur['t1'][-1])
    else:
        tlon, tlat, ttime = lon, lat, times

    fig = go.Figure()

    fig.add_trace(go.Scattermap(
        lon=tlon, lat=tlat, mode='lines',
        line=dict(width=TRACK_WIDTH, color=TRACK_COLOUR),
        name='track', hoverinfo='skip'))

    if SHOW_TRACK_POINTS:
        fig.add_trace(go.Scattermap(
            lon=lon, lat=lat, mode='markers',
            marker=dict(size=3, color='#888', opacity=0.35),
            name='all samples', hoverinfo='skip'))

    # ---- surfacings, coloured by time order -----------------------------
    # A small dated colourbar says what the colours mean; without it the
    # gradient is decorative rather than readable.
    n = tlon.size
    marker = dict(size=SURFACE_MARKER_SIZE, color=np.arange(n),
                  colorscale=SURFACE_CMAP, showscale=False)
    if SHOW_SURFACE_TIMEBAR and n > 1:
        ticks = sorted({0, (n - 1) // 2, n - 1})
        marker.update(
            showscale=True,
            colorbar=dict(title=dict(text='surfacing', side='right',
                                     font=dict(size=10)),
                          thickness=7, len=0.30,
                          x=0.995, xanchor='right',
                          y=0.03, yanchor='bottom',
                          tickmode='array', tickvals=ticks,
                          ticktext=[str(ttime[i])[:10] for i in ticks],
                          tickfont=dict(size=9),
                          outlinewidth=0,
                          bgcolor='rgba(255,255,255,0.65)'))
    fig.add_trace(go.Scattermap(
        lon=tlon, lat=tlat, mode='markers', marker=marker,
        name='surfacings',
        text=[str(t)[:19] for t in ttime],
        hovertemplate='%{text}<br>%{lat:.4f}, %{lon:.4f}<extra></extra>'))

    if cur is not None:
        for tr in current_arrows(cur):
            fig.add_trace(tr)

    fig.add_trace(go.Scattermap(
        lon=[tlon[0]], lat=[tlat[0]], mode='markers',
        marker=dict(size=START_END_SIZE, color='limegreen'), name='start',
        text=[str(ttime[0])[:19]],
        hovertemplate='start<br>%{text}<extra></extra>'))
    fig.add_trace(go.Scattermap(
        lon=[lon[-1]], lat=[lat[-1]], mode='markers',
        marker=dict(size=START_END_SIZE, color='red'), name='last position',
        text=[str(times[-1])[:19]],
        hovertemplate='last position<br>%{text}<extra></extra>'))

    layers = [bathy] if bathy else []

    fig.update_layout(
        map=dict(style=MAP_STYLE, zoom=MAP_ZOOM, layers=layers,
                 center=dict(lon=float(np.nanmean(lon)),
                             lat=float(np.nanmean(lat)))),
        height=740, margin=dict(t=50, l=0, r=0, b=0),
        legend=dict(orientation='h', y=1.02),
        title='Map + average currents')
    return fig


def rose_fig(ts):
    '''Current rose: how often the depth-averaged flow heads each way, and
    how fast. Angle is the direction the current flows TOWARD.'''
    cur = surface_intervals(ts)
    if cur is None:
        return None

    edges = np.arange(0, 360 + ROSE_SECTOR_DEG, ROSE_SECTOR_DEG)
    counts, _ = np.histogram(cur['direction'], bins=edges)
    centres = edges[:-1] + ROSE_SECTOR_DEG / 2
    pct = 100 * counts / max(counts.sum(), 1)

    mean_speed = np.array([
        cur['speed'][(cur['direction'] >= a) & (cur['direction'] < b)].mean()
        if ((cur['direction'] >= a) & (cur['direction'] < b)).any() else 0.0
        for a, b in zip(edges[:-1], edges[1:])])

    fig = go.Figure(go.Barpolar(
        r=pct, theta=centres, width=ROSE_SECTOR_DEG * 0.95,
        marker=dict(color=mean_speed, colorscale=scale('speed'),
                    showscale=True,
                    colorbar=dict(title='mean<br>m/s', thickness=12)),
        customdata=np.stack([counts, mean_speed], axis=-1),
        hovertemplate='toward %{theta:.0f} deg<br>%{r:.1f} %% of intervals '
                      '(%{customdata[0]:.0f})<br>'
                      'mean %{customdata[1]:.3f} m/s<extra></extra>'))

    fig.update_layout(
        template='plotly_white', height=760,
        margin=dict(t=90, l=40, r=40, b=40),
        polar=dict(
            angularaxis=dict(rotation=90, direction='clockwise',
                             tickmode='array',
                             tickvals=[0, 45, 90, 135, 180, 225, 270, 315],
                             ticktext=['N', 'NE', 'E', 'SE',
                                       'S', 'SW', 'W', 'NW']),
            radialaxis=dict(ticksuffix=' %', angle=90)),
        title=f'Depth-averaged current rose diagram')
    return fig


def track_bbox(ts):
    lon = np.asarray(ts['longitude'].values, float)
    lat = np.asarray(ts['latitude'].values, float)
    ok = np.isfinite(lon) & np.isfinite(lat)
    if ok.sum() == 0:
        return None
    return (lon[ok].min(), lon[ok].max(), lat[ok].min(), lat[ok].max())


def load_logs(glider):
    '''-> (surfacings, sensors, devices) DataFrames, or (None, None, None).
    Parquet first, CSV as a fallback so the tab still works if pyarrow is
    missing on the box that runs this.'''
    import pandas as pd
    d = Path(LOG_PARQUET_DIR)
    if not d.exists():
        print(f'   no log directory {d} - skipping the Logs tab')
        return None, None, None
 
    def read(kind):
        pq = d / f'{glider}_{kind}.parquet'
        csv = d / f'{glider}_{kind}.csv'
        try:
            if pq.exists():
                return pd.read_parquet(pq)
            if csv.exists():
                return pd.read_csv(csv, parse_dates=['time'])
        except Exception as e:
            print(f'   could not read {kind}: {e}')
        return None
 
    surf = read('surfacings')
    if surf is None or not len(surf):
        print('   no parsed surfacings - run 03_parse_logs.py first')
        return None, None, None
    surf['time'] = pd.to_datetime(surf['time'])
    sens, devs = read('sensors'), read('devices')
    for df in (sens, devs):
        if df is not None and len(df):
            df['time'] = pd.to_datetime(df['time'])
    print(f'   logs: {len(surf)} dumps, '
          f'{surf["surfacing_id"].nunique()} surfacings')
    return surf, sens, devs
 
 
def _esc(x):
    '''minimal HTML escape - "Because:" strings contain < and >'''
    if x is None:
        return ''
    s = str(x)
    if s in ('nan', 'NaT', 'None', '<NA>'):
        return ''
    return (s.replace('&', '&amp;').replace('<', '&lt;')
             .replace('>', '&gt;').replace('"', '&quot;'))
 
 
def _fmt(v, spec='', dash='-'):
    import pandas as pd
    if v is None or (isinstance(v, float) and not np.isfinite(v)) \
            or pd.isna(v):
        return dash
    try:
        return format(v, spec) if spec else str(v)
    except (TypeError, ValueError):
        return str(v)
 
 
def mark_abort_events(df):
    '''Flag the surfacing where an abort actually HAPPENED.

    The "ABORT HISTORY:" block is sticky - once the glider aborts, every
    later surface dialog reprints the same cause and timestamp until the
    next reset. So the presence of a cause means nothing; the CHANGE does.
    An abort is real on the dump where the abort timestamp differs from the
    previous dump, or where the total-since-reset counter went up.

    The flag is then spread across the whole surfacing, so it survives
    LOG_ONLY_LAST_DUMP filtering out the dump it was first seen on. Row 0
    is never flagged - its history predates the record, so we cannot know
    when that abort happened.
    '''
    import pandas as pd
    df = df.sort_values('time').reset_index(drop=True)
    ev = pd.Series(False, index=df.index)

    if 'abort_last_abort_time' in df:
        s = df['abort_last_abort_time'].astype('string')
        ev |= (s.notna() & (s != s.shift())).fillna(False)
    if 'abort_total_since_reset' in df:
        tot = pd.to_numeric(df['abort_total_since_reset'], errors='coerce')
        ev |= (tot.diff() > 0).fillna(False)
    if len(ev):
        ev.iloc[0] = False
    if 'aborted_now' in df:
        ev |= df['aborted_now'].fillna(False).astype(bool)

    df['abort_event'] = ev
    if 'surfacing_id' in df:
        df['abort_event'] = df.groupby('surfacing_id')['abort_event'] \
                              .transform('any')
    return df


def logbook_html(surf):
    '''The log book: one row per surfacing dump.

    A dump is coloured by what it introduced SINCE THE PREVIOUS ONE, not by
    the cumulative totals - after a week at sea the totals are always large
    and stop meaning anything, whereas "+5 oddities in the last dive" is the
    thing worth looking at. Aborts get the loudest treatment and their own
    filter, because they are the one thing you must not scroll past.
    '''
    df = mark_abort_events(surf)
    n_abort = int(df.loc[df.get('abort_event', False)
                         .fillna(False), 'surfacing_id'].nunique()) \
        if 'surfacing_id' in df else int(df['abort_event'].sum())

    if LOG_ONLY_LAST_DUMP and 'last_dump' in df:
        df = df[df['last_dump'].fillna(True).astype(bool)]
    df = df.sort_values('time', ascending=False).head(LOG_TABLE_MAX_ROWS)

    head = ['time (UTC)', 'segment', 'why it surfaced', 'new problems',
            'GPS', 'waypoint', 'files', 'next dive', 'notes']
    rows = []
    for _, r in df.iterrows():
        sev = r.get('severity', 'ok')
        aborted = bool(r.get('abort_event', False))
        cls = 'abort' if aborted else sev

        badges = ''
        if aborted:
            badges += '<span class="badge abrt">ABORT</span>'
        for kind, lbl in (('new_err', 'err'), ('new_warn', 'warn'),
                          ('new_odd', 'odd')):
            n = r.get(kind, 0)
            n = 0 if n is None or (isinstance(n, float)
                                   and not np.isfinite(n)) else int(n)
            if n > 0:
                badges += f'<span class="badge {lbl}">+{n} {lbl}</span>'
        if not badges:
            badges = '<span class="quiet">clean</span>'

        gps = (f'{_fmt(r.get("gps_lat"), ".4f")}, '
               f'{_fmt(r.get("gps_lon"), ".4f")}')
        if np.isfinite(r.get('gps_age_s', np.nan)):
            gps += f'<span class="quiet"> ({r["gps_age_s"]:.0f}s old)</span>'

        wpt = '-'
        if np.isfinite(r.get('wpt_range_m', np.nan)):
            wpt = (f'{r["wpt_range_m"]:.0f} m @ '
                   f'{_fmt(r.get("wpt_bearing_deg"), ".0f")}&deg;')

        files = '-'
        n_f = r.get('n_files_sent', 0) or 0
        if n_f:
            kb = (r.get('bytes_sent', 0) or 0) / 1000
            files = f'{int(n_f)} <span class="quiet">({kb:.0f} kB)</span>'

        dive = ('-' if not np.isfinite(r.get('dive_in_s', np.nan))
                else f'{r["dive_in_s"]:.0f} s')

        notes = []
        cause = _esc(r.get('abort_last_abort_cause'))
        if aborted and cause:
            notes.append(f'<b class="abrt-note" title="'
                         f'{_esc(r.get("abort_last_abort_details"))}">'
                         f'ABORTED: {cause}</b>')
        elif cause and LOG_SHOW_STICKY_ABORT:
            notes.append(f'<span class="quiet" title="'
                         f'{_esc(r.get("abort_last_abort_details"))}">'
                         f'last abort: {cause}</span>')
        if r.get('resumed'):
            notes.append('resumed')
        if r.get('consci'):
            notes.append('consci')
        n_ood = r.get('n_ood', 0) or 0
        if n_ood:
            notes.append(f'<span title="{_esc(r.get("ood"))}">'
                         f'{int(n_ood)} OOD</span>')

        rows.append(
            f'<tr class="{cls}">'
            f'<td class="mono">{_esc(r["time"])[:19]}</td>'
            f'<td class="mono">{_esc(r.get("segment"))}</td>'
            f'<td>{_esc(r.get("because"))}</td>'
            f'<td>{badges}</td>'
            f'<td class="mono">{gps}</td>'
            f'<td class="mono">{wpt}</td>'
            f'<td class="mono">{files}</td>'
            f'<td class="mono">{dive}</td>'
            f'<td>{" &middot; ".join(notes)}</td>'
            f'</tr>')

    abort_box = ''
    if n_abort:
        abort_box = ('<label class="abrt-toggle">'
                     '<input type="checkbox" id="logaborts" '
                     'onchange="filterLog()"> only aborts '
                     f'<b>({n_abort})</b></label>')
    else:
        abort_box = '<span class="quiet">no aborts in this record</span>'

    thead = ''.join(f'<th>{h}</th>' for h in head)
    return (
        '<div class="logtools">'
        '<input id="logsearch" type="text" placeholder="filter (segment, '
        'reason, note ...)" oninput="filterLog()">'
        '<label><input type="checkbox" id="logproblems" '
        'onchange="filterLog()"> only rows with new problems</label>'
        f'{abort_box}'
        '<span class="quiet" id="logcount"></span></div>'
        f'<div class="logwrap"><table class="logtable" id="logtable">'
        f'<thead><tr>{thead}</tr></thead><tbody>{"".join(rows)}</tbody>'
        '</table></div>')
 
 
def _severity_ramp(hi):
    '''white at zero (so only real events show), then up to `hi`'''
    return [[0.0, 'rgba(255,255,255,1)'], [0.0001, '#fffbe6'],
            [0.35, '#ffe680'], [1.0, hi]]


def device_health_fig(devices):
    '''NEW problems per device per surfacing - all three severities stacked,
    never behind a dropdown.

    Cumulative counters only ever go up, so plotting them shows a staircase
    that says nothing; the delta says which dive broke something. The three
    panels share the time axis and each gets its own colour family, so the
    severity is readable from colour alone. An all-white panel means nothing
    of that kind happened - which is the point of showing it anyway.
    '''
    if devices is None or not len(devices):
        return None

    kinds = [('new_odd', 'oddities', LOG_COL_ODDITY),
             ('new_warn', 'warnings', LOG_COL_WARNING),
             ('new_err', 'errors', LOG_COL_ERROR)]

    mats = {}
    for col, _, _ in kinds:
        if col not in devices:
            return None
        p = devices.pivot_table(index='device', columns='time', values=col,
                                aggfunc='max')
        if DEVICE_HIDE_QUIET:
            p = p[p.fillna(0).sum(axis=1) > 0]
        if p.empty:
            return None
        mats[col] = p

    n_dev = len(mats[kinds[0][0]].index)
    panel = max(DEVICE_PANEL_MIN_HEIGHT, DEVICE_ROW_PX * n_dev)

    fig = make_subplots(rows=len(kinds), cols=1, shared_xaxes=True,
                        vertical_spacing=0.05,
                        subplot_titles=[f'new {lbl}' for _, lbl, _ in kinds])

    for k, (col, lbl, hi) in enumerate(kinds):
        p = mats[col]
        Z = p.values.astype(float)
        fig.add_trace(go.Heatmap(
            z=Z, x=list(p.columns), y=list(p.index),
            colorscale=_severity_ramp(hi),
            zmin=0, zmax=max(np.nanmax(Z), 1), xgap=1, ygap=1,
            colorbar=dict(title=dict(text=lbl, side='right',
                                     font=dict(size=10)),
                          thickness=10, len=1 / len(kinds) - 0.06,
                          y=1 - (k + 0.5) / len(kinds),
                          tickfont=dict(size=9)),
            hovertemplate='%{y}<br>%{x|%d %b %H:%M}<br>'
                          '+%{z:.0f} ' + lbl + '<extra></extra>'),
            row=k + 1, col=1)
        fig.update_yaxes(autorange='reversed', tickfont=dict(size=10),
                         row=k + 1, col=1)

    for ann in fig.layout.annotations:      # subplot titles, left-aligned
        ann.update(x=0, xanchor='left', font=dict(size=12.5))

    fig.update_layout(
        height=panel * len(kinds) + 130, template='plotly_white',
        margin=dict(t=95, l=145, r=20, b=55), hovermode='closest',
        title=dict(text='NEW problems per device, per surfacing '
                        '(white = nothing happened)',
                   x=0.5, xanchor='center'))
    return fig
 
 
def log_sensors_fig(sensors):
    '''Every sensor the surface dialog reports, one at a time from a
    dropdown. x is the time the value was MEASURED where that is known
    (report time minus the "secs ago"), which is often minutes earlier.'''
    if sensors is None or not len(sensors):
        return None
    df = sensors
    if 'stale' in df:
        df = df[~df['stale'].fillna(False).astype(bool)]
    df = df[np.isfinite(df['value'])]
    if not len(df):
        return None
 
    names = sorted(df['sensor'].unique())
    tcol = 'measured_at' if 'measured_at' in df else 'time'
 
    def series(name):
        s = df[df['sensor'] == name].sort_values(tcol)
        return ([str(t)[:19] for t in s[tcol]],
                [round(float(v), 6) for v in s['value']],
                (s['units'].iloc[0] if len(s) else ''))
 
    first = ('m_battery' if 'm_battery' in names else names[0])
    x, y, u = series(first)
 
    fig = go.Figure(go.Scattergl(
        x=x, y=y, mode='lines+markers',
        line=dict(width=1.2, color=GLIDER_MEASURED_COLOUR),
        marker=dict(size=4, color=GLIDER_MEASURED_COLOUR),
        hovertemplate='%{x}<br>%{y}<extra></extra>', showlegend=False))
 
    buttons = []
    for n in names:
        xs, ys, un = series(n)
        buttons.append(dict(
            label=n, method='update',
            args=[{'x': [xs], 'y': [ys]},
                  {'yaxis.title.text': f'{n} [{un}]',
                   'title.text': f'{n}  [{un}]  -  {len(xs)} readings'}]))
 
    fig.update_layout(
        updatemenus=[dict(buttons=buttons, direction='down', showactive=True,
                          x=0, xanchor='left', y=1.10, yanchor='top',
                          active=names.index(first))],
        annotations=[dict(text='sensor', x=-0.005, y=1.12, xref='paper',
                          yref='paper', showarrow=False, xanchor='right')],
        height=LOG_SENSOR_HEIGHT, template='plotly_white',
        plot_bgcolor=SCATTER_BG, xaxis_title='time',
        yaxis_title=f'{first} [{u}]',
        margin=dict(t=95, l=70, r=20, b=50),
        title=dict(text=f'{first}  [{u}]  -  {len(x)} readings',
                   x=0.5, xanchor='center'))
    return fig
 
 
def log_key_fig(sensors):
    '''The handful of sensors you check every surfacing, stacked and sharing
    the zoom - battery, charge, vacuum, iridium signal and so on.'''
    if sensors is None or not len(sensors):
        return None
    df = sensors
    if 'stale' in df:
        df = df[~df['stale'].fillna(False).astype(bool)]
    df = df[np.isfinite(df['value'])]
    have = [s for s in LOG_KEY_SENSORS if (df['sensor'] == s).any()]
    if not have:
        return None
    tcol = 'measured_at' if 'measured_at' in df else 'time'
 
    titles = []
    for s in have:
        u = df[df['sensor'] == s]['units'].iloc[0]
        titles.append(f'{s} [{u}]')
 
    fig = make_subplots(rows=len(have), cols=1, shared_xaxes=True,
                        vertical_spacing=min(0.02, 0.8 / max(len(have) - 1, 1)),
                        subplot_titles=titles)
    for k, s in enumerate(have):
        d = df[df['sensor'] == s].sort_values(tcol)
        fig.add_trace(go.Scattergl(
            x=[str(t)[:19] for t in d[tcol]],
            y=[round(float(v), 6) for v in d['value']],
            mode='lines+markers',
            line=dict(width=1.2, color=GLIDER_MEASURED_COLOUR),
            marker=dict(size=3.5, color=GLIDER_MEASURED_COLOUR),
            showlegend=False, name=s,
            hovertemplate='%{x}<br>%{y}' f'<extra>{s}</extra>'),
            row=k + 1, col=1)
 
    for ann in fig.layout.annotations:
        ann.update(x=0, xanchor='left', font=dict(size=12.5))

    # white grid on grey: the axis LINE and the zeroline have to go white too,
    # otherwise plotly_white leaves dark grey strokes across the panels
    grid = dict(showgrid=True, gridcolor=LOG_KEY_GRID,
                gridwidth=LOG_KEY_GRID_WIDTH,
                zeroline=True, zerolinecolor=LOG_KEY_GRID,
                zerolinewidth=LOG_KEY_GRID_WIDTH,
                linecolor=LOG_KEY_GRID, showline=False)
    fig.update_xaxes(**grid)
    fig.update_yaxes(**grid)
    fig.update_xaxes(title_text='time', row=len(have), col=1)

    fig.update_layout(
        height=LOG_KEY_ROW_HEIGHT * len(have) + 120, template='plotly_white',
        plot_bgcolor=LOG_KEY_BG,
        margin=dict(t=70, l=70, r=20, b=45),
        hovermode='x unified', dragmode='zoom',
        title=dict(text='housekeeping sensors from the surface dialog',
                   x=0.5, xanchor='center'))
    return fig

def load_battery(glider):
    '''-> (dict, series, dives) from 03b_battery.py, or (None, None, None)'''
    import pandas as pd
    d = Path(BATTERY_DIR)
    j = d / f'{glider}_battery.json'
    if not j.exists():
        print('   no battery json - run 03b_battery.py first')
        return None, None, None
    try:
        b = json.loads(j.read_text())
        s = pd.read_parquet(d / f'{glider}_battery_series.parquet')
        s.index = pd.to_datetime(s.index)
        dv = pd.read_parquet(d / f'{glider}_battery_dives.parquet')
        if len(dv):
            dv['end'] = pd.to_datetime(dv['end'])
    except Exception as e:
        print(f'   could not read the battery files: {e}')
        return None, None, None
    print(f'   battery: {b["now"]["pct_left"]:.1f} % left, '
          f'headline "{b["headline"]}"')
    return b, s, dv
 
 
def _urgency(days):
    if days is None:
        return 'ok'
    return ('urgent' if days < BATT_URGENT_DAYS
            else 'warn' if days < BATT_WARN_DAYS else 'ok')
 
 
def battery_summary_html(b):
    '''The numbers you actually want at a glance, with the recover-by date
    sized and coloured by how close it is. Everything else on this tab is
    supporting evidence for this one line.'''
    now, cap = b['now'], b['battery']['f_coulomb_battery_capacity']
    head = b['headline']
    rec = b['projections'][head]['recovery']
    crit = b['projections'][head]['critical']
    cls = _urgency(rec.get('days'))
 
    def card(label, value, sub='', extra=''):
        return (f'<div class="bcard {extra}"><div class="blab">{label}</div>'
                f'<div class="bval">{value}</div>'
                f'<div class="bsub">{sub}</div></div>')
 
    recd = ('unknown' if not rec.get('date')
            else f'{rec["date"][8:10]} {_MON[int(rec["date"][5:7])]} '
                 f'{rec["date"][11:16]}')
    critd = ('' if not crit.get('date')
             else f'critical {crit["date"][8:10]} '
                  f'{_MON[int(crit["date"][5:7])]} {crit["date"][11:16]}')
 
    rate = b['rates'][head]['ah_per_day']
    m = b.get('measured') or {}
    dive_txt = '-'
    if m.get('recent'):
        r = m['recent']
        dive_txt = (f'{r["dive_hours"]:.2f} h &middot; '
                    f'{r["ah_per_dive"]:.2f} Ah')
 
    cards = (
        card('battery left', f'{now["pct_left"]:.1f} %',
             f'{now["ah_used"]:.1f} of {cap:.0f} Ah used')
        + card('start recovery by', recd,
               f'{rec["days"]:.1f} days from now &middot; {critd}'
               if rec.get('days') is not None else critd,
               extra=f'wide {cls}')
        + card('consumption', f'{rate:.2f} Ah/day',
               f'from: {head}')
        + card('typical dive', dive_txt,
               f'{m.get("recent", {}).get("n_dives", 0)} recent of '
               f'{b.get("n_dives", 0)} dives')
        + card('pack', b['battery']['name'].replace('lithium ', 'Li '),
               f'{cap:.0f} Ah &middot; {b["battery"]["detection"]}')
        + card('flying', b['config']['config_name'],
               f'{b["config"]["description"]} ({b["config"]["detection"]})')
    )
 
    warn = ''
    if cls == 'urgent':
        warn = ('<div class="bbanner urgent">Recovery window is inside '
                f'{BATT_URGENT_DAYS} days.</div>')
    elif cls == 'warn':
        warn = ('<div class="bbanner warn">Recovery window is inside '
                f'{BATT_WARN_DAYS} days.</div>')
 
    v = b.get('voltage') or {}
    note = ('The recover-by date comes from the coulomb counter. The voltage '
            'panel is a cross-check only: lithium packs hold voltage almost '
            'flat and then fall away quickly, so a straight line through '
            'volts reads optimistic until it suddenly does not.')
    if v.get('undervolts', {}).get('days') is not None:
        note += (f' That fit currently says {v["undervolts"]["days"]:.0f} days '
                 f'to {b["battery"]["undervolts"]} V.')
 
    return (f'{warn}<div class="bcards">{cards}</div>'
            f'<div class="bnote">{note}</div>')
 
 
_MON = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
        7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}
 
 
def battery_fig(b, series, dives):
    '''Three panels: cumulative Ah with the projection and the recovery
    window, the consumption rate, and the pack voltage.
 
    The panels do NOT share an x axis on purpose - only the top one runs
    into the future, and stretching the other two to match would squeeze
    the measured record into a corner.'''
    import pandas as pd
    if series is None or not len(series):
        return None
 
    cap = b['battery']['f_coulomb_battery_capacity']
    now_t = pd.Timestamp(b['now']['time'])
    now_ah = b['now']['ah_used']
    head = b['headline']
    amp = 'm_coulomb_amphr_total'
    volt = 'm_battery'
 
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=False, vertical_spacing=0.085,
        subplot_titles=['amp-hours used, measured then projected',
                        'consumption rate',
                        'pack voltage (cross-check only)'])
 
    # ---------- row 1: Ah + projection ----------
    fig.add_trace(go.Scatter(
        x=series.index, y=series[amp].round(2), mode='lines',
        line=dict(width=2, color=BATT_MEASURED_COLOUR), name='measured',
        hovertemplate='%{x|%d %b %H:%M}<br>%{y:.1f} Ah<extra></extra>'),
        row=1, col=1)
 
    horizon = max([(b['projections'][k]['shutdown'].get('days') or 0)
                   for k in b['rates']] + [1]) * 1.15
    tp = pd.date_range(now_t, now_t + pd.Timedelta(days=horizon), periods=40)
    dd = (tp - now_t) / pd.Timedelta('1D')
    for name, r in b['rates'].items():
        y = now_ah + r['ah_per_day'] * dd
        y = np.where(y <= cap * 1.02, y, np.nan)
        is_head = name == head
        fig.add_trace(go.Scatter(
            x=tp, y=np.round(y, 1), mode='lines',
            line=dict(width=3 if is_head else 1.3, dash='dash',
                      color=BATT_HEADLINE_COLOUR if is_head
                      else BATT_FAN_COLOUR),
            name=f'{name} ({r["ah_per_day"]:.1f} Ah/d)',
            legendgroup='proj',
            hovertemplate='%{x|%d %b %H:%M}<br>%{y:.0f} Ah<br>'
                          f'{r["note"]}<extra>{name}</extra>'), row=1, col=1)
 
    for key, col in (('recovery', '#e69500'), ('critical', '#c62828'),
                     ('shutdown', '#666666')):
        th = b['thresholds'][key]
        fig.add_hline(y=th['ah'], line=dict(color=col, width=1.4,
                                            dash='solid' if key != 'shutdown'
                                            else 'dot'),
                      annotation_text=f'{key} - {th["pct_left"]:.0f}% left',
                      annotation_position='top left',
                      annotation_font=dict(size=10, color=col),
                      row=1, col=1)
 
    # add_shape/add_annotation rather than add_vline: add_vline with an
    # annotation asks plotly for the shape's midpoint, which it computes as
    # sum(x)/len(x). That starts the sum at integer 0, and 0 + Timestamp is
    # an error in recent pandas - so the convenience wrapper breaks on any
    # datetime axis. Drawing the line and the label separately never goes
    # near that code.
    def _vline(x, colour, width, dash=None, text=None):
        fig.add_shape(type='line', x0=x, x1=x, y0=0, y1=1, yref='y domain',
                      line=dict(color=colour, width=width, dash=dash),
                      row=1, col=1)
        if text:
            fig.add_annotation(x=x, y=1.0, yref='y domain', text=text,
                               showarrow=False, yanchor='bottom',
                               xanchor='center',
                               font=dict(size=11, color=colour),
                               row=1, col=1)

    rec = b['projections'][head]['recovery']
    crit = b['projections'][head]['critical']
    if rec.get('date'):
        rt = pd.Timestamp(rec['date'])
        if crit.get('date'):
            fig.add_shape(type='rect', x0=rt, x1=pd.Timestamp(crit['date']),
                          y0=0, y1=1, yref='y domain',
                          fillcolor='#c62828', opacity=0.12, line_width=0,
                          layer='below', row=1, col=1)
        _vline(rt, '#c62828', 2.5, text=f'recover by {rt:%d %b %H:%M}')
    _vline(now_t, '#444', 1, dash='dot')
    fig.update_yaxes(title_text='Ah used', range=[0, cap * 1.05],
                     row=1, col=1)
 
    # ---------- row 2: rate ----------
    rr = b.get('roll_rate')
    if rr:
        fig.add_trace(go.Scatter(
            x=pd.to_datetime(rr['time']), y=rr['ah_per_day'], mode='lines',
            line=dict(width=1.4, color=BATT_MEASURED_COLOUR),
            name='observed (24 h window)', connectgaps=False,
            hovertemplate='%{x|%d %b %H:%M}<br>%{y:.2f} Ah/day'
                          '<extra></extra>'), row=2, col=1)
    if dives is not None and len(dives):
        fig.add_trace(go.Scatter(
            x=dives.end, y=dives.ah_per_day.round(3), mode='markers',
            marker=dict(size=5, color='#999999'),
            name=f'per dive (n={len(dives)}, surface hops excluded)',
            customdata=np.stack([dives.dive_hours, dives.ah_per_dive,
                                 dives.get('max_depth',
                                           pd.Series(np.nan, dives.index))],
                                axis=-1),
            hovertemplate='%{x|%d %b %H:%M}<br>%{y:.2f} Ah/day<br>'
                          '%{customdata[0]:.2f} h, %{customdata[1]:.2f} Ah<br>'
                          'max depth %{customdata[2]:.0f} m<extra></extra>'),
            row=2, col=1)
        n_recent = (b.get('measured', {}) or {}).get('recent', {}) \
            .get('n_dives', 0)
        if n_recent:
            tail = dives.tail(n_recent)
            fig.add_trace(go.Scatter(
                x=tail.end, y=tail.ah_per_day.round(3), mode='markers',
                marker=dict(size=10, color='rgba(0,0,0,0)',
                            line=dict(width=2, color=BATT_HEADLINE_COLOUR)),
                name=f'last {n_recent} (drives the projection)',
                hoverinfo='skip'), row=2, col=1)
    for k, f in (b.get('fits') or {}).items():
        if f:
            fig.add_hline(y=f['ah_per_day'],
                          line=dict(color='rgba(31,119,180,0.55)', width=1,
                                    dash='dash'),
                          annotation_text=f'{k}: {f["ah_per_day"]:.2f}',
                          annotation_position='right',
                          annotation_font=dict(size=9),
                          row=2, col=1)
    fig.update_yaxes(title_text='Ah / day', row=2, col=1)
 
    # ---------- row 3: voltage ----------
    if volt in series:
        fig.add_trace(go.Scatter(
            x=series.index, y=series[volt].round(3), mode='lines',
            line=dict(width=1.6, color=BATT_MEASURED_COLOUR),
            name='pack voltage',
            hovertemplate='%{x|%d %b %H:%M}<br>%{y:.2f} V<extra></extra>'),
            row=3, col=1)
    for key, col in (('undervolts', '#e69500'), ('Vcutoff', '#c62828')):
        fig.add_hline(y=b['battery'][key],
                      line=dict(color=col, width=1.3, dash='dash'),
                      annotation_text=f'{key} {b["battery"][key]} V',
                      annotation_position='bottom left',
                      annotation_font=dict(size=10, color=col),
                      row=3, col=1)
    fig.update_yaxes(title_text='volts', row=3, col=1)
    fig.update_xaxes(title_text='time', row=3, col=1)
 
    for ann in fig.layout.annotations[:3]:
        ann.update(x=0, xanchor='left', font=dict(size=12.5))
 
    fig.update_layout(
        height=BATT_ROW_HEIGHT * 3 + 150, template='plotly_white',
        margin=dict(t=60, l=70, r=20, b=45), dragmode='zoom',
        legend=dict(orientation='h', y=-0.06, x=0, xanchor='left',
                    font=dict(size=10)),
        hovermode='closest')
    return fig

#%% ============================================================
#   page template (tabs)
#   ------------------------------------------------------------
#   @@placeholders@@ instead of str.format, so the CSS/JS braces stay readable
#   ============================================================
PAGE = '''<!doctype html><html><head><meta charset="utf-8">
<title>@@glider@@ - glider data</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
 :root{--bg:#fafafa;--fg:#222;--hdr:#354370;--nav:#e8ecef;--hint:#666}
 body{font-family:system-ui,sans-serif;margin:0;background:var(--bg);color:var(--fg)}
 header{padding:14px 20px;background:var(--hdr);color:#fff}
 header h1{margin:0;font-size:19px}
 header .meta{font-size:12.5px;opacity:.85;margin-top:4px}
 header a{color:#9fd0ff;margin-right:12px}
 nav{display:flex;gap:2px;background:var(--nav);padding:0 14px}
 nav button{border:0;padding:11px 18px;background:none;cursor:pointer;
   font-size:14px;border-bottom:3px solid transparent;color:var(--fg)}
 nav button.on{background:var(--bg);border-bottom-color:#4da3ff;font-weight:600}
 .tab{display:none;padding:12px} .tab.on{display:block}
 .hint{font-size:12.5px;color:var(--hint);padding:2px 4px 8px}
 .subnav{margin:0 0 8px 4px}
 .subnav button{font-size:13px;padding:5px 12px;margin-right:6px;cursor:pointer;
   border:1px solid rgba(128,128,128,.45);background:transparent;
   color:var(--fg);border-radius:4px}
 .subnav button.on{background:#4da3ff;border-color:#4da3ff;color:#fff}
 .sub{display:none} .sub.on{display:block}
 .logtools{margin:0 0 8px 4px;display:flex;gap:14px;align-items:center;
   flex-wrap:wrap;font-size:12.5px}
 .logtools input[type=text]{padding:5px 9px;min-width:280px;font-size:13px;
   border:1px solid rgba(128,128,128,.45);border-radius:4px;
   background:transparent;color:var(--fg)}
 .logwrap{max-height:78vh;overflow:auto;border:1px solid rgba(128,128,128,.3);
   border-radius:5px}
 table.logtable{border-collapse:collapse;width:100%;font-size:12.5px}
 table.logtable th{position:sticky;top:0;background:var(--nav);
   text-align:left;padding:8px 10px;font-weight:600;z-index:2;
   border-bottom:1px solid rgba(128,128,128,.45)}
 table.logtable td{padding:6px 10px;border-bottom:1px solid rgba(128,128,128,.18);
   vertical-align:top}
 table.logtable tbody tr:hover{background:rgba(77,163,255,.10)}
 table.logtable td.mono{font-family:ui-monospace,Menlo,Consolas,monospace;
   white-space:nowrap}
 tr.oddity  td:first-child{box-shadow:inset 4px 0 0 #ffe680}
 tr.warning td:first-child{box-shadow:inset 4px 0 0 #ffb020}
 tr.error   td:first-child{box-shadow:inset 4px 0 0 #ff4d4d}
 tr.warning{background:rgba(255,176,32,.13)}
 tr.error{background:rgba(255,77,77,.18)}
 /* an abort is the one row you must not scroll past: full-width magenta
    wash, a heavy bar both sides, bold text and a border top and bottom */
 tr.abort{background:rgba(192,38,211,.22);font-weight:600}
 tr.abort td{border-top:2px solid #c026d3;border-bottom:2px solid #c026d3}
 tr.abort td:first-child{box-shadow:inset 7px 0 0 #c026d3}
 tr.abort td:last-child{box-shadow:inset -7px 0 0 #c026d3}
 tr.abort:hover{background:rgba(192,38,211,.32)}
 .abrt-note{color:#7a0f8c}
 .abrt-toggle{padding:2px 8px;border-radius:4px;
   background:rgba(192,38,211,.14);border:1px solid rgba(192,38,211,.45)}
 .badge{display:inline-block;padding:1px 7px;margin:1px 3px 1px 0;
   border-radius:9px;font-size:11px;font-weight:600;white-space:nowrap;
   color:#3a2c00}
 .badge.odd{background:#ffe680} .badge.warn{background:#ffb020}
 .badge.err{background:#ff4d4d;color:#fff}
 .badge.abrt{background:#c026d3;color:#fff;letter-spacing:.5px}
 .quiet{color:var(--hint);font-weight:400}
 .bcards{display:flex;flex-wrap:wrap;gap:10px;margin:2px 4px 10px}
 .bcard{flex:1 1 150px;padding:9px 13px;border-radius:6px;
   border:1px solid rgba(128,128,128,.3);background:rgba(128,128,128,.06)}
 .bcard.wide{flex:1 1 260px}
 .bcard.urgent{border-color:#c62828;background:rgba(198,40,40,.13)}
 .bcard.warn{border-color:#e69500;background:rgba(230,149,0,.13)}
 .blab{font-size:10.5px;text-transform:uppercase;letter-spacing:.6px;
   color:var(--hint)}
 .bval{font-size:20px;font-weight:600;margin:2px 0 1px;line-height:1.2}
 .bcard.urgent .bval{color:#c62828} .bcard.warn .bval{color:#a86800}
 .bsub{font-size:11px;color:var(--hint)}
 .bbanner{padding:8px 13px;border-radius:6px;margin:2px 4px 9px;
   font-weight:600;font-size:13px}
 .bbanner.urgent{background:#c62828;color:#fff}
 .bbanner.warn{background:#ffb020;color:#3a2c00}
 .bnote{font-size:11.5px;color:var(--hint);margin:0 4px 10px;max-width:900px}
</style></head><body>
<header>
  <h1>@@glider@@</h1>
  <div class="meta">@@segtext@@ &nbsp;|&nbsp; data up to <b>@@last@@</b>
      &nbsp;|&nbsp; page built @@built@@</div>
  <div class="meta">@@links@@</div>
</header>
<nav>@@navbuttons@@</nav>
@@tabs@@
'''

PAGE += '''<script>
 function show(i){
   document.querySelectorAll('.tab').forEach((t,k)=>t.classList.toggle('on',k==i));
   document.querySelectorAll('nav button').forEach((b,k)=>b.classList.toggle('on',k==i));
   window.dispatchEvent(new Event('resize'));
 }
 function showSub(tab,i){
   document.querySelectorAll('#'+tab+' .sub').forEach((x,k)=>x.classList.toggle('on',k==i));
   document.querySelectorAll('#'+tab+' .subnav button').forEach((x,k)=>x.classList.toggle('on',k==i));
   window.dispatchEvent(new Event('resize'));
 }
 function filterLog(){
   var t = document.getElementById('logsearch');
   var q = t ? t.value.toLowerCase() : '';
   var onlyBad = document.getElementById('logproblems');
   onlyBad = onlyBad && onlyBad.checked;
   var onlyAbort = document.getElementById('logaborts');
   onlyAbort = onlyAbort && onlyAbort.checked;
   var rows = document.querySelectorAll('#logtable tbody tr'), n = 0;
   rows.forEach(function(r){
     var cls = r.className || '';
     var isAbort = cls.indexOf('abort') >= 0;
     var bad = cls && cls !== 'ok';
     var hit = !q || r.textContent.toLowerCase().indexOf(q) >= 0;
     var show = hit && (!onlyBad || bad) && (!onlyAbort || isAbort);
     r.style.display = show ? '' : 'none';
     if (show) n++;
   });
   var c = document.getElementById('logcount');
   if (c) c.textContent = n + ' / ' + rows.length + ' surfacings';
 }
'''

PAGE += '''
 show(0);
 document.querySelectorAll('.sub-group').forEach(g=>showSub(g.id,0));
 if (document.getElementById('logtable')) filterLog();
</script></body></html>'''


#%% ============================================================
#   build
#   ============================================================
def embed(fig):
    return pio.to_html(fig, include_plotlyjs=False, full_html=False,
                       config={'displaylogo': False, 'responsive': True})


def segment_text():
    if SEGMENTS is None:
        return 'whole deployment'
    if isinstance(SEGMENTS, (tuple, list)):
        return f'segments {SEGMENTS[0]}-{SEGMENTS[1]}'
    return (f'last {abs(SEGMENTS)} segments' if SEGMENTS < 0
            else f'segment {SEGMENTS}')


def build(glider, bathy):
    print(f'\n=== {glider} ===')
    t0, t1 = segment_window()
    grid = load_grid(glider, t0, t1)
    ts = load_ts(glider, t0, t1)
    last = str(ts.time.values[-1])[:19]
    print(f'   {grid.time.size} profiles, {ts.time.size} samples, '
          f'last measurement {last}')

    has_pos = {'longitude', 'latitude'} <= set(ts.data_vars) | set(ts.coords)
    terrain = load_bathy_terrain(bbox=track_bbox(ts) if has_pos else None) \
        if SHOW_TERRAIN else None

    tabs = nav = ''
    i = 0

    def add(name, html, hint):
        nonlocal tabs, nav, i
        tabs += f'<div class="tab"><div class="hint">{hint}</div>{html}</div>\n'
        nav += f'<button onclick="show({i})">{name}</button>'
        i += 1

    sec = sections_fig(grid)
    if sec is not None:
        add('Sections', embed(sec),
            'each panel zooms on its own | dashed grey lines = real profiles, '
            'everything between them is interpolated')

    sci = scatter_fig(ts, SCIENCE_VARS, DEFAULT_SCIENCE, 'pick the axes above')
    tsd = ts_fig(ts)
    if sci is not None:
        if tsd is not None:
            inner = ('<div id="scitab" class="sub-group"><div class="subnav">'
                     '<button onclick="showSub(\'scitab\',0)">scatter</button>'
                     '<button onclick="showSub(\'scitab\',1)">T-S diagram</button>'
                     '</div>'
                     f'<div class="sub">{embed(sci)}</div>'
                     f'<div class="sub">{embed(tsd)}</div></div>')
        else:
            inner = embed(sci)
        add('Science', inner,
            'drag to zoom | "colour" picks which variable tints the markers')

    gld = glider_fig(ts)
    if gld is not None:
        add('Glider', embed(gld),
            'all panels share the zoom - drag on any one | orange = measured, '
            'dark = commanded | grey bands = descending')

    cur = curtain_fig(grid, ts, terrain)
    if cur is not None:
        add('3D', embed(cur),
            'drag to rotate, scroll to zoom | the slider picks a time RANGE '
            '(single chunk or several in a row)')

    mp = map_fig(ts, bathy)
    rose = rose_fig(ts) if SHOW_CURRENT_ROSE else None
    if mp is not None:
        if rose is not None:
            inner = ('<div id="maptab" class="sub-group"><div class="subnav">'
                     '<button onclick="showSub(\'maptab\',0)">map</button>'
                     '<button onclick="showSub(\'maptab\',1)">current rose</button>'
                     '</div>'
                     f'<div class="sub">{embed(mp)}</div>'
                     f'<div class="sub">{embed(rose)}</div></div>')
        else:
            inner = embed(mp)
        add('Map + average currents', inner,
            'scroll to zoom, drag to pan | red arrows = depth-averaged '
            'current per surface-to-surface interval')
        
    if SHOW_LOGS:
        surf, sens, devs = load_logs(glider)
        if surf is not None:
            panes = [('log book', logbook_html(surf))]
            dh = device_health_fig(devs)
            if dh is not None:
                panes.append(('device health', embed(dh)))
            kf = log_key_fig(sens)
            if kf is not None:
                panes.append(('housekeeping', embed(kf)))
            sf = log_sensors_fig(sens)
            if sf is not None:
                panes.append(('all sensors', embed(sf)))
 
            btns = ''.join(
                f'<button onclick="showSub(\'logtab\',{k})">{name}</button>'
                for k, (name, _) in enumerate(panes))
            body = ''.join(f'<div class="sub">{html}</div>'
                           for _, html in panes)
            inner = (f'<div id="logtab" class="sub-group">'
                     f'<div class="subnav">{btns}</div>{body}</div>')
            add('Logs', inner,
                'from the surface dialog | coloured rows = the glider picked '
                'up a NEW error / warning / oddity on that dive')

    if SHOW_BATTERY:
        bat, bser, bdiv = load_battery(glider)
        if bat is not None:
            bfig = battery_fig(bat, bser, bdiv)
            inner = battery_summary_html(bat) + (embed(bfig) if bfig else '')
            add('Battery', inner,
                'projection from the coulomb counter | the red line is the '
                'latest you should start recovery, the shaded band runs to '
                'critical')
            
    links = ('gliders: ' + ' '.join(f'<a href="{g}.html">{g}</a>'
                                    for g in GLIDERS)) if len(GLIDERS) > 1 else ''

    html = PAGE
    for k, v in (('glider', glider), ('segtext', segment_text()),
                 ('last', last),
                 ('built', dt.datetime.now().strftime('%Y-%m-%d %H:%M')),
                 ('links', links), ('navbuttons', nav), ('tabs', tabs)):
        html = html.replace(f'@@{k}@@', str(v))

    out = OUT_DIR / f'{glider}.html'
    out.write_text(html)
    print(f'   -> {out}  ({out.stat().st_size/1e6:.1f} MB)')
    return out


# %%
if __name__ == '__main__':
    BATHY = bathy_layer()
    pages = [build(g, BATHY) for g in GLIDERS]
    print(f'\nopen: {pages[0]}')
# %%