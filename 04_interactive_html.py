'''
04_interactive_html.py
One self-contained web page per glider (no server - just open the html).

  SECTIONS  - contour (filled + lines) depth-vs-time panels on a uniform
              time axis. Dashed grey vertical lines mark the profiles that
              were really measured, down to the deepest bin they reached;
              everything between them is interpolated. Gaps longer than
              MAX_GAP_HOURS stay empty. Each panel zooms on its own.
  SCIENCE   - scatter (pick x / y / colour) + a T-S diagram with potential
              density contours, both above a depth-vs-time context strip.
  GLIDER    - the same for the engineering variables. "+ glider depth"
              overlays the dive profile on the scatter itself.
  3D        - multibeam bathymetry as terrain with the section hung along
              the track as a curtain. Unmeasured parts are transparent.
  MAP       - bathymetry image + island outline + track + last position.

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

SECTION_MAX_COLS = 1500     # hard cap on columns per panel, applied after
                            # REFINE_MINUTES. This is the main file-size and
                            # browser-speed guard: go.Contour runs marching
                            # squares in JS, so a few thousand columns times
                            # ~100 depth bins is already slow. Raise carefully.

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

SECTION_MAX_COLS = 600      # was 1500 (selkie used 1103). 600 columns over a
                            # 4-day deployment is ~10 min per column.

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

N_TIME_WINDOWS = 3          # was 6. Each slider step stores a full copy of
                            # the curtain geometry (X, Y, Z, F) - this is the
                            # 5.2 MB "sliders" column.

# ---- colours ------------------------------------------------------------
CMAP_PER_VAR = {'temperature': 'thermal', 'conductivity': 'haline',
                'salinity': 'haline', 'potential_density': 'dense',
                'chlorophyll': 'algae', 'cdom': 'matter',
                'backscatter_700': 'turbid', 'oxygen_concentration': 'oxy',
                'par': 'solar', 'depth': 'deep'}
                            # cmocean name per variable; anything not listed
                            # falls back to 'thermal'. Needs `cmocean`,
                            # otherwise everything becomes Viridis.
COLOUR_SCHEMES = ['per variable (cmocean)', 'thermal', 'haline', 'dense',
                  'deep', 'balance', 'Viridis', 'Plasma', 'Turbo']
                            # entries of the in-page "colours" dropdown.
CLIM_PCT = (2, 98)          # percentile clipping for every colour limit.
                            # (0, 100) = full range, outliers wash it out.
MARKER_SIZE = 6             # scatter markers (Science / Glider / T-S)
MARKER_SIZE_3D = 3          # markers in the 3D point fallback

# ---- Science / Glider tabs ---------------------------------------------
SCIENCE_VARS = ['temperature', 'salinity', 'potential_density', 'conductivity',
                'chlorophyll', 'cdom', 'backscatter_700',
                'oxygen_concentration', 'par', 'depth', 'time',
                'longitude', 'latitude']
GLIDER_VARS  = ['depth', 'pitch', 'roll', 'heading', 'battery_position',
                'oil_volume', 'fin', 'altitude', 'commanded_heading',
                'commanded_fin', 'time', 'longitude', 'latitude']
                            # choices in the x / y / colour dropdowns.
DEFAULT_SCIENCE = ('temperature', 'depth')   # (x, y) shown on first load
DEFAULT_GLIDER  = ('time', 'depth')

SHOW_DEPTH_STRIP = True     # thin depth-vs-time panel under every scatter, so
                            # the dive pattern is visible whatever the axes are.
DEPTH_STRIP_FRAC = 0.18     # its share of the figure height
DEPTH_STRIP_COLOUR = 'rgba(60,60,60,0.75)'
DEPTH_STRIP_WIDTH = 0.8

DEPTH_OVERLAY = True        # adds an "+ glider depth" toggle button that draws
                            # the dive profile ON the scatter itself, on a
                            # second (right, reversed) y axis. Off on load,
                            # click the button to show it. It is plotted
                            # against TIME, so it only lines up when x = time.
DEPTH_OVERLAY_COLOUR = "#c0d5d7"
DEPTH_OVERLAY_WIDTH = 1.0

# ---- T-S diagram --------------------------------------------------------
TS_DENSITY_CONTOURS = True  # sigma0 isolines in the background (needs gsw)
TS_N_DENSITY_LINES = 12     # roughly how many isolines
TS_COLOUR_BY = 'depth'      # variable used to colour the T-S points

# ---- 3D tab -------------------------------------------------------------
BATHY_XYZ = config.ROOT / 'data' / 'Pelagia_bathymetry' / \
            'Bathymetry-Curacao_64PE430-500-529_30m-grid_ASCII.XYZ.xyz'
                            # ASCII "lon lat depth", depth negative downward.
BATHY_STRIDE = 4            # decimate the 30 m grid (4 -> ~120 m). Lower =
                            # sharper seabed, much heavier page.
BATHY_PAD_DEG = 0.02        # crop the terrain to the track bbox + this pad.
                            # None = keep the whole file (heavy!).
BATHY_CMAP = 'deep'         # cmocean scale for the seabed
BATHY_CACHE = True          # cache the gridded terrain as .npz next to the
                            # xyz; delete the .npz after changing BATHY_STRIDE.
SHOW_TERRAIN = True         # False = curtain only, builds much faster
Z_EXAGGERATION = 0.55       # vertical stretch of the 3D scene
N_TIME_WINDOWS = 6          # slider steps for the curtain (+ 'whole period')
HEIGHT_3D = 900             # px
SCENE_TRANSPARENT = True    # no grey walls behind the 3D scene - the axis
                            # panes become transparent and the page background
                            # shows through.
SCENE_GRID_COLOUR = 'rgba(120,120,120,0.15)'   # faint 3D gridlines; use
                            # 'rgba(0,0,0,0)' to hide them completely.

# ---- map tab ------------------------------------------------------------
COASTLINE_SHP = config.ROOT / 'data' / 'cuw_adm0' / 'CUW_adm0.shp'
BATHY_PNG     = config.ROOT / 'data' / 'bathymetry_PE500.png'
BATHY_BOUNDS  = (11.911966662, -69.244978161, 12.451537991, -68.610831513)
                            # (south, west, north, east) of BATHY_PNG; the png
                            # is base64-embedded, so it drives the file size.
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
                            # your usual zoom. (0.10 at 0.3 m/s = 0.03 deg,
                            # about 3 km.) The east component is divided by
                            # cos(lat) so the arrow points the true way on a
                            # Mercator basemap.
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
START_END_SIZE = 18

SHOW_CURRENT_ROSE = True    # a "current rose" sub-tab next to the map
ROSE_SECTOR_DEG = 15        # sector width; 15 -> 24 petals

# ---- page ---------------------------------------------------------------
OUT_DIR = config.HTML       # <glider>.html is written here


#%% ============================================================
#   setup
#   ============================================================
from pathlib import Path
import base64
import bisect
import datetime as dt
import json

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

    fill_idx, fill_scales, n_traces = [], [], 0

    for k, v in enumerate(have):
        A = grid[v].values
        if FILL_GAPS:
            A = fill(A, times)
        lo, hi = clim(A)
        Z = np.round(interp_to(A, times, tf), 4)
        Z, depths = crop_empty_rows(Z, grid.depth.values)
        if SECTION_DEPTH_STRIDE > 1:
            Z, depths = Z[::SECTION_DEPTH_STRIDE], depths[::SECTION_DEPTH_STRIDE]
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
            n_traces += 1
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
            fill_idx.append(n_traces)     # only these get recoloured
            fill_scales.append(cs)
            n_traces += 1

        if SHOW_PROFILE_LINES:
            tr = profile_lines(A, times, grid.depth.values)
            if tr is not None:
                fig.add_trace(tr, row=k + 1, col=1)
                n_traces += 1

        fig.update_yaxes(autorange='reversed', title_text='depth [m]',
                         row=k + 1, col=1)
        fig.update_xaxes(showticklabels=True, row=k + 1, col=1)

    buttons = []
    for s in COLOUR_SCHEMES:
        if s.startswith('per variable'):
            cs_list = fill_scales
        else:
            base = scale(s) if SMOOTH_SECTIONS else stepped(scale(s))
            cs_list = [base] * len(fill_idx)
        buttons.append(dict(label=s, method='restyle',
                            args=[{'colorscale': cs_list}, fill_idx]))

    fig.update_layout(
        updatemenus=[dict(buttons=buttons, direction='down', showactive=True,
                          x=0, xanchor='left', y=1.03, yanchor='bottom')],
        annotations=list(fig.layout.annotations) +
        [dict(text='colours', x=-0.005, y=1.04, xref='paper', yref='paper',
              showarrow=False, xanchor='right')],
        height=SECTION_ROW_HEIGHT * len(have) + 110,
        template='plotly_white', dragmode='zoom',
        margin=dict(t=100, l=65, r=20, b=45))
    return fig


#%% ============================================================
#   TABS 2/3 - scatter (+ depth context strip)
#   ============================================================
def column(ts, name):
    if name == 'time':
        return [str(t)[:19] for t in ts.time.values]
    v = np.asarray(ts[name].values, float)
    return [None if not np.isfinite(x) else round(float(x), 6) for x in v]


def depth_strip_trace(ts):
    """Faint depth-vs-time line in the panel under the scatter, so the dive
    pattern is visible whatever the scatter axes are set to."""
    if 'depth' not in ts:
        return None
    return go.Scattergl(
        x=[str(t)[:19] for t in ts.time.values],
        y=column(ts, 'depth'), mode='lines',
        line=dict(width=DEPTH_STRIP_WIDTH, color=DEPTH_STRIP_COLOUR),
        name='depth', showlegend=False,
        hovertemplate='%{x}<br>%{y:.1f} m<extra></extra>')


def depth_overlay_trace(ts):
    """Dive profile drawn ON the scatter itself, on the secondary (right,
    reversed) y axis. Hidden until the "+ glider depth" button is clicked."""
    if 'depth' not in ts:
        return None
    return go.Scattergl(
        x=[str(t)[:19] for t in ts.time.values],
        y=column(ts, 'depth'), mode='lines',
        line=dict(width=DEPTH_OVERLAY_WIDTH, color=DEPTH_OVERLAY_COLOUR),
        name='glider depth', showlegend=False, visible=False,
        hovertemplate='%{x}<br>%{y:.1f} m<extra>glider depth</extra>')


def scatter_fig(ts, varlist, default, title):
    have = [v for v in varlist if v == 'time' or v in ts]
    if not have:
        return None
    cols = {v: column(ts, v) for v in have}
    xd = default[0] if default[0] in have else have[0]
    yd = default[1] if default[1] in have else have[-1]
    cd = next((v for v in ('temperature', 'depth') if v in have), have[0])
    num = lambda v: [np.nan if q is None else q for q in cols[v]]

    has_depth = 'depth' in ts
    strip = SHOW_DEPTH_STRIP and has_depth
    overlay = DEPTH_OVERLAY and has_depth

    # a secondary y axis on row 1 is what carries the depth overlay
    if strip:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=False,
                            vertical_spacing=0.09,
                            row_heights=[1 - DEPTH_STRIP_FRAC, DEPTH_STRIP_FRAC],
                            specs=[[{'secondary_y': True}], [{}]],
                            subplot_titles=[None, 'dive pattern (depth vs time)'])
    elif overlay:
        fig = make_subplots(rows=1, cols=1, specs=[[{'secondary_y': True}]])
    else:
        fig = make_subplots(rows=1, cols=1)

    main = go.Scattergl(
        x=cols[xd], y=cols[yd], mode='markers',
        marker=dict(size=MARKER_SIZE, color=num(cd), colorscale=scale_for(cd),
                    showscale=True, opacity=0.85, line=dict(width=0),
                    colorbar=dict(title=cd, thickness=12,
                                  len=(1 - DEPTH_STRIP_FRAC) if strip else 1,
                                  y=1, yanchor='top')),
        hovertemplate='%{x}<br>%{y}<extra></extra>', showlegend=False)
    fig.add_trace(main, row=1, col=1)          # trace 0 - the dropdowns target it

    ovl_i = None
    if overlay:
        tr = depth_overlay_trace(ts)
        if tr is not None:
            fig.add_trace(tr, row=1, col=1, secondary_y=True)
            ovl_i = len(fig.data) - 1
            fig.update_yaxes(title_text='glider depth [m]', autorange='reversed',
                             showgrid=False, secondary_y=True, row=1, col=1)

    if strip:
        tr = depth_strip_trace(ts)
        if tr is not None:
            fig.add_trace(tr, row=2, col=1)
        fig.update_yaxes(autorange='reversed', title_text='depth [m]',
                         row=2, col=1)
        fig.update_xaxes(title_text='time', row=2, col=1)

    # the dropdowns must restyle trace 0 (the scatter) only
    def menu(kind, active, x):
        b = []
        for v in have:
            if kind == 'x':
                args = [{'x': [cols[v]]}, {'xaxis.title.text': v}, [0]]
            elif kind == 'y':
                args = [{'y': [cols[v]]},
                        {'yaxis.title.text': v,
                         'yaxis.autorange': 'reversed' if v == 'depth' else True},
                        [0]]
            else:
                args = [{'marker.color': [num(v)],
                         'marker.colorscale': [scale_for(v)],
                         'marker.colorbar.title.text': v}, {}, [0]]
            b.append(dict(label=v, method='update', args=args))
        return dict(buttons=b, direction='down', showactive=True, x=x,
                    xanchor='left', y=1.11, yanchor='top',
                    active=have.index(active))

    sch = [dict(label=s, method='restyle',
                args=[{'marker.colorscale': [scale_for(cd) if s.startswith('per')
                                             else scale(s)]}, [0]])
           for s in COLOUR_SCHEMES]

    menus = [menu('x', xd, 0.0), menu('y', yd, 0.20), menu('c', cd, 0.40),
             dict(buttons=sch, direction='down', showactive=True,
                  x=0.62, xanchor='left', y=1.11, yanchor='top')]
    if ovl_i is not None:
        # one highlighted toggle: click = show, click again = hide
        menus.append(dict(
            type='buttons', direction='left', showactive=True,
            x=0.84, xanchor='left', y=1.11, yanchor='top',
            bgcolor='#4da3ff', bordercolor='#4da3ff',
            font=dict(color='#ffffff', size=12.5),
            buttons=[dict(label='+ glider depth', method='restyle',
                          args=[{'visible': True}, [ovl_i]],
                          args2=[{'visible': False}, [ovl_i]])]))

    fig.update_layout(
        updatemenus=menus,
        annotations=list(fig.layout.annotations) +
        [dict(text=t, x=p, y=1.13, xref='paper', yref='paper',
              showarrow=False, xanchor='right')
         for t, p in (('x', -0.005), ('y', 0.195), ('colour', 0.395),
                      ('scheme', 0.615))],
        height=860, template='plotly_white',
        margin=dict(t=105, l=60, r=70 if ovl_i is not None else 20, b=50),
        title=title)
    fig.update_xaxes(title_text=xd, row=1, col=1)
    fig.update_yaxes(title_text=yd, row=1, col=1,
                     **(dict(secondary_y=False) if overlay else {}))
    if yd == 'depth':
        fig.update_yaxes(autorange='reversed', row=1, col=1,
                         **(dict(secondary_y=False) if overlay else {}))
    return fig


#%% ============================================================
#   T-S diagram
#   ============================================================
def ts_fig(ts):
    '''Salinity on x, temperature on y, potential density as isolines.'''
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
                showscale=False, hoverinfo='skip', name='sigma0'))
        except ImportError:
            print('   gsw not installed - T-S without density contours')

    cvar = TS_COLOUR_BY if TS_COLOUR_BY in ts else 'depth'
    C = np.asarray(ts[cvar].values, float)[ok] if cvar in ts else None
    fig.add_trace(go.Scattergl(
        x=S, y=T, mode='markers',
        marker=dict(size=MARKER_SIZE, opacity=0.8, line=dict(width=0),
                    color=C if C is not None else 'steelblue',
                    colorscale=scale_for(cvar) if C is not None else None,
                    showscale=C is not None,
                    colorbar=dict(title=cvar, thickness=12)),
        hovertemplate='S %{x:.3f}<br>T %{y:.3f}<extra></extra>',
        showlegend=False))

    fig.update_layout(
        xaxis_title='salinity', yaxis_title='temperature [degC]',
        height=780, template='plotly_white',
        margin=dict(t=60, l=60, r=20, b=50),
        title='T-S diagram (thin lines = potential density sigma0)')
    return fig


#%% ============================================================
#   bathymetry terrain
#   ============================================================
def load_bathy_terrain(path=BATHY_XYZ, stride=BATHY_STRIDE,
                       bbox=None, pad=BATHY_PAD_DEG):
    '''Read the ASCII "lon lat depth" grid and reshape it to a regular 2D
    array. Cached as .npz next to the source.'''
    path = Path(path)
    if not path.exists():
        print(f'   no {path.name} - 3D without terrain')
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


def _wlabel(a, b):
    f = '%d %b %H:%M'
    return (dt.datetime.utcfromtimestamp(float(a)).strftime(f) + '  ->  ' +
            dt.datetime.utcfromtimestamp(float(b)).strftime(f))


def curtain_fig(grid, ts, terrain):
    have = [v for v in SECTION_VARS if v in grid]
    if 'longitude' not in grid or 'latitude' not in grid or not have:
        print('   no position on the grid - 3D falls back to points')
        return scatter3d_fig(ts, terrain)
    lon, lat, z, fields = curtain_arrays(grid, have)
    t = tsec(grid.time.values)

    edges = np.linspace(t[0], t[-1], N_TIME_WINDOWS + 1)
    windows = [('whole period', np.ones(t.size, bool))]
    for a, b in zip(edges[:-1], edges[1:]):
        keep = (t >= a) & (t <= b)
        if keep.sum() >= 2:
            windows.append((_wlabel(a, b), keep))

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
        colorbar=dict(title=first, thickness=12),
        hovertemplate='%{x:.4f}, %{y:.4f}<br>%{z:.0f} m<br>'
                      '%{surfacecolor:.3f}<extra></extra>'))

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

    sch = [dict(label=s, method='restyle',
                args=[{'colorscale': [stepped(scale_for(first))
                                      if s.startswith('per')
                                      else stepped(scale(s))]}, [cur_i]])
           for s in COLOUR_SCHEMES]

    tvis = ([dict(label='terrain on', method='restyle',
                  args=[{'visible': [True]}, [ti]]),
             dict(label='terrain off', method='restyle',
                  args=[{'visible': [False]}, [ti]])] if ti is not None else [])

    menus = [dict(buttons=var_buttons, direction='down', showactive=True,
                  x=0, xanchor='left', y=1.05, yanchor='bottom'),
             dict(buttons=sch, direction='down', showactive=True,
                  x=0.22, xanchor='left', y=1.05, yanchor='bottom')]
    if tvis:
        menus.append(dict(buttons=tvis, direction='down', showactive=True,
                          x=0.46, xanchor='left', y=1.05, yanchor='bottom'))

    fig.update_layout(
        updatemenus=menus,
        sliders=[dict(active=0, currentvalue=dict(prefix='period: '),
                      pad=dict(t=18), steps=steps, x=0.02, len=0.96)],
        annotations=[dict(text='variable', x=-0.005, y=1.06, xref='paper',
                          yref='paper', showarrow=False, xanchor='right'),
                     dict(text='colours', x=0.215, y=1.06, xref='paper',
                          yref='paper', showarrow=False, xanchor='right')],
        scene=dict(xaxis_title='longitude', yaxis_title='latitude',
                   zaxis_title='depth [m]', aspectmode='manual',
                   aspectratio=dict(x=1, y=1, z=Z_EXAGGERATION),
                   camera=dict(eye=dict(x=1.4, y=-1.4, z=0.8)),
                   **scene_axes()),
        paper_bgcolor='rgba(0,0,0,0)' if SCENE_TRANSPARENT else None,
        height=HEIGHT_3D, margin=dict(t=80, l=0, r=0, b=10),
        title='seabed + measured curtain (drag to fly, scroll to zoom)')
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
            x=0, xanchor='left', y=1.05, yanchor='bottom')],
        scene=dict(xaxis_title='longitude', yaxis_title='latitude',
                   zaxis_title='depth [m]', aspectmode='manual',
                   aspectratio=dict(x=1, y=1, z=Z_EXAGGERATION),
                   **scene_axes()),
        paper_bgcolor='rgba(0,0,0,0)' if SCENE_TRANSPARENT else None,
        height=HEIGHT_3D, margin=dict(t=70, l=0, r=0, b=0), title='3D track')
    return fig


#%% ============================================================
#   TAB 5 - map
#   ============================================================
def coastline_geojson(path):
    path = Path(path)
    if not path.exists():
        print(f'   no {path.name} - skipping the coastline')
        return None
    try:
        import geopandas as gpd
        return json.loads(gpd.read_file(path).to_crs('EPSG:4326').to_json())
    except ImportError:
        pass
    try:
        import shapefile
        sf = shapefile.Reader(str(path))
        return {'type': 'FeatureCollection',
                'features': [{'type': 'Feature', 'properties': {},
                              'geometry': s.__geo_interface__}
                             for s in sf.shapes()]}
    except Exception as e:
        print(f'   coastline not read ({e})')
        return None


def bathy_layer():
    p = Path(BATHY_PNG)
    if not p.exists():
        print(f'   no {p.name} - map without bathymetry')
        return None
    s, w, n, e = BATHY_BOUNDS
    uri = 'data:image/png;base64,' + base64.b64encode(p.read_bytes()).decode()
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
        if not (np.isfinite(lon[[a, b]]).all() and np.isfinite(lat[[a, b]]).all()):
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


def map_fig(ts, coast, bathy):
    '''Basemap + bathymetry image + coastline + grey track through the
    surfacings, coloured by time + depth-averaged current arrows.'''
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

    # surfacings coloured by time order
    fig.add_trace(go.Scattermap(
        lon=tlon, lat=tlat, mode='markers',
        marker=dict(size=SURFACE_MARKER_SIZE,
                    color=np.arange(tlon.size), colorscale=SURFACE_CMAP,
                    showscale=False),
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

    layers = []
    if bathy:
        layers.append(bathy)
    if coast:
        layers.append(dict(source=coast, type='line', color='black',
                           line=dict(width=1.5)))

    fig.update_layout(
        map=dict(style=MAP_STYLE, zoom=MAP_ZOOM, layers=layers,
                 center=dict(lon=float(np.nanmean(lon)),
                             lat=float(np.nanmean(lat)))),
        height=740, margin=dict(t=50, l=0, r=0, b=0),
        legend=dict(orientation='h', y=1.02),
        title='surface events and depth-averaged currents '
              '(green = start, red = last position)')
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
        title=f'depth-averaged current rose - direction flowed TOWARD, '
              f'{cur["u"].size} surface intervals '
              f'(first {CURRENT_SKIP_FIRST} skipped)')
    return fig

def track_bbox(ts):
    lon = np.asarray(ts['longitude'].values, float)
    lat = np.asarray(ts['latitude'].values, float)
    ok = np.isfinite(lon) & np.isfinite(lat)
    if ok.sum() == 0:
        return None
    return (lon[ok].min(), lon[ok].max(), lat[ok].min(), lat[ok].max())


#%% ============================================================
#   page template (tabs)
#   ------------------------------------------------------------
#   @@placeholders@@ instead of str.format, so the CSS/JS braces stay readable
#   ============================================================
PAGE = '''<!doctype html><html><head><meta charset="utf-8">
<title>@@glider@@ - glider data</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
 :root{--bg:#fafafa;--fg:#222;--hdr:#12354f;--nav:#e8ecef;--hint:#666}
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
'''

PAGE += '''
 show(0);
 document.querySelectorAll('.sub-group').forEach(g=>showSub(g.id,0));
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


def build(glider, coast, bathy):
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
            'drag to zoom | "+ glider depth" overlays the dive profile '
            '(it is plotted against time)')

    gld = scatter_fig(ts, GLIDER_VARS, DEFAULT_GLIDER, 'pick the axes above')
    if gld is not None:
        add('Glider', embed(gld),
            'drag to zoom | "+ glider depth" overlays the dive profile '
            '(it is plotted against time)')

    cur = curtain_fig(grid, ts, terrain)
    if cur is not None:
        add('3D', embed(cur),
            'drag to rotate, scroll to zoom | slider picks the time window')

    mp = map_fig(ts, coast, bathy)
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
        add('Map', inner,
            'scroll to zoom, drag to pan | red arrows = depth-averaged '
            'current per surface-to-surface interval')

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


# COAST = coastline_geojson(COASTLINE_SHP)
# BATHY = bathy_layer()
# pages = [build(g, COAST, BATHY) for g in GLIDERS]
# print(f'\nopen: {pages[0]}')

# %%

if __name__ == '__main__':
    COAST = coastline_geojson(COASTLINE_SHP)
    BATHY = bathy_layer()
    pages = [build(g, COAST, BATHY) for g in GLIDERS]
    print(f'\nopen: {pages[0]}')
# %%
