'''
02_plots_full_timeseries.py
Plots of the WHOLE deployment (or any time window you choose).

Reads:  L0-gridfiles/*.nc   (science sections)
        L0-timeseries/*.nc  (engineering / machinery)
Writes: plots/*.png

Run it as a notebook (cells are marked with #%%) or from a terminal:
    python 02_plots_full_timeseries.py
Everything you'd normally want to change is in the SETTINGS cell.
'''
#%% ============================================================
#   SETTINGS - edit this cell only
#   ============================================================
import config          # glider name + paths live in config.py

# ---- time window ----
START = None       # None = from the beginning, or '2026-07-17' / '2026-07-17 06:00'
END   = None       # None = until the end

# ---- which science sections to draw ----
# One figure per group; a variable is skipped if it isn't in the data.
# Available (depends on your sensors + deployment.yml):
#   temperature, conductivity, salinity, potential_density,
#   chlorophyll, cdom, backscatter_700, oxygen_concentration, par
SECTION_GROUPS = {
    'sections_physics': ['temperature', 'salinity', 'potential_density'],
    'sections_biology': ['chlorophyll', 'oxygen_concentration', 'par'],
}
ISOPYCNALS = True       # density contours on top of the physics figure
N_CONTOURS = 6

# ---- which engineering variables to draw ----
# (measured, commanded, label, unit conversion)  -- commanded can be []
RAD2DEG = 180 / 3.141592653589793
MACHINERY = [
    (['battery_position', 'm_battpos'], ['commanded_battery_position', 'c_battpos'], 'battery pos [in]', 1),
    (['oil_volume', 'm_de_oil_vol'],    ['commanded_oil_volume', 'c_de_oil_vol'],    'oil volume [cc]', 1),
    (['fin', 'm_fin'],                  ['commanded_fin', 'c_fin'],                  'fin [deg]', RAD2DEG),
    (['heading', 'm_heading'],          ['commanded_heading', 'c_heading'],          'heading [deg]', RAD2DEG),
    (['pitch', 'm_pitch'],              [],                                          'pitch [deg]', RAD2DEG),
    (['roll', 'm_roll'],                [],                                          'roll [deg]', RAD2DEG),
    (['altitude', 'm_altitude'],        [],                                          'altitude [m]', 1),
]

# ---- looks ----
DERIVE_SALINITY = True   # compute salinity/density from cond+temp on the grid
                         # (the realtime feed usually can't do it itself)
CLIM_PCT   = (2, 98)     # colour range percentiles (2,98 hides outliers)
FIGWIDTH   = 12
ROWHEIGHT  = 2.6
SHOW_POINTS = True       # dots on lines = actual samples
SHOW_DEPTH  = True       # grey glider depth behind every machinery panel
SAVE = True

#%% ============================================================
#   setup
#   ============================================================
from pathlib import Path
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

plt.rcParams.update({
    'savefig.dpi': 200, 'font.size': 9, 'axes.titleweight': 'bold',
    'axes.grid': True, 'grid.alpha': 0.25,
    'axes.spines.top': False, 'axes.spines.right': False,
    'figure.constrained_layout.use': True})

try:
    import cmocean.cm as cmo
    CMAPS = {'temperature': cmo.thermal, 'conductivity': cmo.haline,
             'salinity': cmo.haline, 'potential_density': cmo.dense,
             'chlorophyll': cmo.algae, 'cdom': cmo.matter,
             'backscatter_700': cmo.turbid, 'oxygen_concentration': cmo.oxy,
             'par': cmo.solar}
except ImportError:
    print('tip: `conda install -c conda-forge cmocean` for nicer colours')
    CMAPS = {}

cmap_of = lambda v: CMAPS.get(v, plt.cm.viridis)
pick = lambda ds, names: next((n for n in names if n in ds), None)


def clim(a):
    a = np.asarray(a); a = a[np.isfinite(a)]
    return (0, 1) if a.size == 0 else tuple(np.percentile(a, CLIM_PCT))


def time_axis(ax):
    loc = mdates.AutoDateLocator()
    ax.xaxis.set_major_locator(loc)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc))


def save(fig, name):
    if SAVE:
        f = config.PLOTS / f'{name}.png'
        fig.savefig(f)
        print(f'   saved -> {f}')


#%% ============================================================
#   load the gridded science data
#   ============================================================
print(f'Glider: {config.GLIDER}')
grid = xr.open_dataset(config.newest_nc(config.L0_GRID, config.GLIDER))
if START or END:
    grid = grid.sel(time=slice(START, END))

print(f'\n{grid.time.size} profiles, from {str(grid.time.values[0])[:16]} '
      f'to {str(grid.time.values[-1])[:16]}, down to {float(grid.depth.max()):.0f} m')
print('how much data each variable actually has:')
for v in grid.data_vars:
    if grid[v].ndim == 2:
        n = int(np.isfinite(grid[v].values).sum())
        pct = 100 * n / grid[v].size
        print(f'   {v:22s} {n:8d} values ({pct:4.1f}% of the grid)')


#%% ============================================================
#   compute salinity + density from conductivity & temperature
#   (the realtime feed rarely has cond+temp+pressure at the same instant,
#    so pyglider's own salinity comes out nearly empty; on the grid we can
#    use the depth axis as pressure and get a full field)
#   ============================================================
if DERIVE_SALINITY and 'conductivity' in grid and 'temperature' in grid:
    try:
        import gsw
        C = grid['conductivity'].values * 10          # S/m -> mS/cm
        T = grid['temperature'].values
        P = np.broadcast_to(grid.depth.values[:, None], C.shape)   # dbar ~ m
        lon = float(np.nanmean(grid.longitude)) if 'longitude' in grid else 0.0
        lat = float(np.nanmean(grid.latitude)) if 'latitude' in grid else 0.0
        SP = gsw.SP_from_C(C, T, P)
        SA = gsw.SA_from_SP(SP, P, lon, lat)
        CT = gsw.CT_from_t(SA, T, P)
        before = int(np.isfinite(grid['salinity'].values).sum()) if 'salinity' in grid else 0
        grid['salinity'] = (('depth', 'time'), SP,
                            {'units': 'g/kg', 'comment': 'computed on grid, pressure = depth'})
        grid['potential_density'] = (('depth', 'time'), gsw.sigma0(SA, CT) + 1000,
                                     {'units': 'kg m-3', 'comment': 'sigma0 + 1000, computed on grid'})
        print(f'\nsalinity computed from conductivity+temperature: '
              f'{int(np.isfinite(SP).sum())} values (file had {before})')
    except ImportError:
        print('\ngsw not installed (`conda install -c conda-forge gsw`) - '
              'plotting only what is in the file')

#%% ============================================================
#   science sections
#   ============================================================
def _contour_colour(bg_value, cmap, vmin, vmax):
    '''black on light background, white on dark background'''
    if not np.isfinite(bg_value):
        return 'w'
    frac = np.clip((bg_value - vmin) / max(vmax - vmin, 1e-12), 0, 1)
    r, g, b = cmap(frac)[:3]
    f = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    lum = 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
    return 'k' if lum > 0.4 else 'w'


def plot_sections(varlist, figname, isopycnals=False):
    '''One panel per variable, depth vs time.'''
    have = [v for v in varlist if v in grid]
    skipped = [v for v in varlist if v not in grid]
    if skipped:
        print(f'   not available, skipped: {", ".join(skipped)}')
    if not have:
        print(f'   nothing to plot for {figname}'); return None
    fig, axs = plt.subplots(len(have), 1, sharex=True, sharey=True,
                            figsize=(FIGWIDTH, ROWHEIGHT * len(have)))
    axs = np.atleast_1d(axs)
    for ax, v in zip(axs, have):
        vmin, vmax = clim(grid[v].values)
        pcm = ax.pcolormesh(grid.time, grid.depth, grid[v], cmap=cmap_of(v),
                            vmin=vmin, vmax=vmax, shading='nearest',
                            rasterized=True)
        if isopycnals and 'potential_density' in grid and v != 'potential_density':
            pden = grid['potential_density'].values - 1000
            levels = np.linspace(*clim(pden), N_CONTOURS)
            dl = np.diff(levels).mean() if len(levels) > 1 else 1
            for lev in levels:                      # one call per level so the
                near = np.abs(pden - lev) < dl / 2  # colour can follow the map
                bg = np.nanmedian(grid[v].values[near]) if near.any() else np.nan
                ax.contour(grid.time, grid.depth, pden, levels=[lev],
                           colors=[_contour_colour(bg, cmap_of(v), vmin, vmax)],
                           linewidths=0.45, alpha=0.7)
        ax.set_ylabel('depth [m]')
        cb = fig.colorbar(pcm, ax=ax, pad=0.01)
        cb.set_label(f"{v}\n[{grid[v].attrs.get('units', '')}]", fontsize=8)
    axs[0].invert_yaxis()
    time_axis(axs[-1])
    fig.suptitle(f'{config.GLIDER} - {figname.replace("_", " ")}')
    save(fig, figname)
    return fig


for figname, varlist in SECTION_GROUPS.items():
    print(f'\nplotting {figname}: {", ".join(varlist)}')
    plot_sections(varlist, figname,
                  isopycnals=ISOPYCNALS and 'physics' in figname)

#%% ============================================================
#   load the timeseries (engineering data)
#   ============================================================
ts = xr.open_dataset(config.newest_nc(config.L0_TS, config.GLIDER))
if START or END:
    ts = ts.sel(time=slice(START, END))
print(f'timeseries: {ts.time.size} samples')

#%% ============================================================
#   machinery
#   ============================================================
def plot_machinery(figname='machinery'):
    rows = [(pick(ts, m), pick(ts, c), lab, sc) for m, c, lab, sc in MACHINERY
            if pick(ts, m) or pick(ts, c)]
    absent = [lab for m, c, lab, _ in MACHINERY
              if not (pick(ts, m) or pick(ts, c))]
    if absent:
        print(f'   not in the data, skipped: {", ".join(absent)}')
    if not rows:
        print('   no engineering variables found'); return None
    zn = pick(ts, ['depth', 'm_depth', 'pressure'])
    fig, axs = plt.subplots(len(rows), 1, sharex=True,
                            figsize=(FIGWIDTH, 1.8 * len(rows)))
    axs = np.atleast_1d(axs)
    for ax, (mn, cn, lab, sc) in zip(axs, rows):
        if SHOW_DEPTH and zn:                    # grey depth behind everything
            z = ts[zn].values; okz = np.isfinite(z)
            axz = ax.twinx()
            axz.plot(ts.time.values[okz], z[okz], lw=0.5, color='0.6',
                     alpha=0.7, zorder=0)
            axz.invert_yaxis(); axz.grid(False)
            axz.set_ylabel('depth [m]', fontsize=6.5, color='0.5')
            axz.tick_params(labelsize=6.5, colors='0.5')
            ax.set_zorder(axz.get_zorder() + 1); ax.patch.set_visible(False)
        for nm, colour, ls in ((mn, 'tab:blue', '-'), (cn, 'tab:red', '--')):
            if not nm:
                continue
            v = ts[nm].values * sc
            ok = np.isfinite(v)
            ax.plot(ts.time.values[ok], v[ok], ls, lw=0.6, color=colour,
                    marker='.' if SHOW_POINTS else None, ms=3,
                    label=f'{nm} ({ok.sum()} points)')
        ax.set_ylabel(lab, fontsize=8)
        ax.legend(fontsize=6.5, loc='upper right', frameon=False)
    time_axis(axs[-1])
    fig.suptitle(f'{config.GLIDER} - engineering '
                 f'(grey = depth, dots = real samples)')
    save(fig, figname)
    return fig

print('\nplotting machinery')
plot_machinery()

#%% ============================================================
#   dive track + seafloor
#   ============================================================
def plot_dive_track(figname='dive_track'):
    '''Depth vs time. Realtime files often carry depth only while the glider
    is diving, so gaps are missing DATA, not missing dives - the point counts
    and the second panel make that visible.'''
    cands = [n for n in ['depth', 'm_depth', 'pressure', 'sci_water_pressure']
             if n in ts]
    if not cands:
        print('   no depth in the timeseries'); return None
    fig, axs = plt.subplots(2, 1, sharex=True, figsize=(FIGWIDTH, 6),
                            height_ratios=[2, 1])
    colours = ['tab:blue', 'tab:green', 'tab:purple', 'tab:brown']
    for n, col in zip(cands, colours):
        z = np.abs(ts[n].values.astype(float))
        ok = np.isfinite(z)
        print(f'   {n:20s} {ok.sum():7d} points, max {np.nanmax(z):.0f}')
        axs[0].plot(ts.time.values[ok], z[ok], '-', lw=0.6, color=col,
                    marker='.' if SHOW_POINTS else None, ms=2.5,
                    label=f'{n} ({ok.sum()} points)')
    an = pick(ts, ['altitude', 'm_altitude'])
    if an:
        z = np.abs(ts[cands[0]].values.astype(float))
        sf = z + ts[an].values
        ok2 = np.isfinite(sf)
        axs[0].plot(ts.time.values[ok2], sf[ok2], '.', ms=3, color='k',
                    label=f'seafloor = depth + altimeter ({ok2.sum()} points)')
    axs[0].invert_yaxis(); axs[0].set_ylabel('depth [m]')
    axs[0].legend(frameon=False, fontsize=7)

    # where do samples actually exist?  (1 = there is a measurement)
    for n, col in zip(cands, colours):
        ok = np.isfinite(ts[n].values.astype(float))
        axs[1].plot(ts.time.values[ok], np.full(ok.sum(), n), '|', ms=6,
                    color=col)
    axs[1].set_ylabel('sample present', fontsize=8)
    axs[1].tick_params(labelsize=7)
    time_axis(axs[1])
    fig.suptitle(f'{config.GLIDER} - dive track '
                 f'(gaps = not transmitted, not missing dives)')
    save(fig, figname)
    return fig

print('\nplotting dive track')
plot_dive_track()

plt.show()   # keeps figures open when run from a terminal

# %%
