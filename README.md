# Slocum glider data pipeline

Turns Slocum glider binaries into netcdf, plots and an interactive web page,
using [pyglider](https://pyglider.readthedocs.io).

Several gliders are processed side by side — every output folder has one
subfolder per glider, and the glider is chosen per process with an
environment variable, so nothing collides.

```
config.py                     <- paths + glider selection (the one file you may edit)
fresh_start.py                <- run first: makes folders, checks the setup
deployment_<glider>.yml       <- metadata + sensor -> variable mapping (you write this)
sensor_list_<glider>.txt      <- written by 00, do not edit by hand
run_gliders.py                <- runs every step for every glider

data/<download folder>/       <- drop the dockserver folders here
cache/<glider>/               \
rawnc/<glider>/segments/       |  created automatically
rawnc/<glider>/merged/         |  (all gitignored)
L0-timeseries/<glider>/        |
L0-profiles/<glider>/          |
L0-gridfiles/<glider>/         |
plots/<glider>/                |
interactive/<glider>/          |
.state/<glider>/              /   <- what has already been processed
```

## Fresh start

After cloning:

```bash
conda create -n gliderwork python=3.12
conda activate gliderwork
conda install -c conda-forge pyglider dbdreader cmocean gsw plotly pyshp netcdf4

python fresh_start.py
```

`fresh_start.py` creates every folder, checks the packages, and prints a
checklist of what is still missing. It changes nothing that already exists,
so you can rerun it whenever something looks off.

It will tell you to do these, in this order:

1. **Write `deployment_<glider>.yml`.** Copy the example, rename it, set the
   `metadata:` block (`glider_name` must match the file name) and, under
   `netcdf_variables:`, each entry's `source:` = the Slocum sensor name.
   You do *not* have to remove sensors your glider lacks — `01` skips them
   with a warning.
2. **Put the download folder in `data/`,** exactly as it comes off the
   dockserver: `data/<glider>-from-glider-<timestamp>/`. The glider name in
   the folder name is how the scripts tell your gliders apart. Add as many
   folders as you have — `01` reads *all* of them.
3. **Optional, for the map and 3D tabs:** `data/bathymetry_PE500.png`,
   `data/cuw_adm0/CUW_adm0.shp`, `data/Pelagia_bathymetry/*.xyz`. Everything
   still works without them, those tabs just get simpler.
4. Rerun `python fresh_start.py` until it is happy.

## Running

Everything, every glider:

```bash
python run_gliders.py       # set GLIDERS at the top of the file first
```

Or one glider, one step at a time:

```bash
GLIDER=selkie python 00_build_sensor_list.py   # which sensors carry data
GLIDER=selkie python 01_process_to_nc.py       # binaries -> netcdf
GLIDER=selkie python 02_plots_full_timeseries.py
GLIDER=selkie python 04_interactive_html.py    # the web page
python 05_all_gliders.py                       # one landing page for all
```

`GLIDER` defaults to whatever is set in `config.py`, so on Windows or in an
IDE you can just edit that line instead. Every script also runs cell-by-cell
in VS Code / Jupyter (`#%%` markers).

| script | what it does |
|---|---|
| `00_build_sensor_list.py` | Looks inside the binaries, writes `sensor_list_<glider>.txt` with only the sensors that actually carry measurements. Reports what the yml asked for and could not find. Needed once per glider. |
| `01_process_to_nc.py` | Binaries → netcdf. **Incremental** — see below. Quick look figure in `plots/<glider>/`. |
| `02_plots_full_timeseries.py` | Static figures for the whole deployment. The first cell holds everything worth changing. |
| `04_interactive_html.py` | `interactive/<glider>/<glider>.html` — a normal file, no server. |
| `05_all_gliders.py` | `interactive/all_gliders.html` — a button per glider, each page loaded on first click. |
| `06_html_weight.py` | Diagnostic: where the megabytes in the html go. |

## Incremental processing

`01` fingerprints each stage and skips work it has already done, so a rerun
after a new download only costs the new segments.

- **rawnc/segments/** is an archive: converted binaries are only ever added.
  It is rebuilt only if the sensor list, the yml, or realtime/recovered mode
  changed.
- The merge runs on a throwaway copy, because pyglider's `merge_rawnc`
  consumes its input directory.
- timeseries, profiles and grid are single files, so they are rewritten —
  but only when something upstream actually moved.

Each stage prints why it ran: `never run`, `settings or upstream changed`,
`output missing`, or `up to date`. `TIMING = True` prints seconds per stage.

To redo something:

```python
FORCE = 'timeseries'   # in 01: that stage and everything after it
FORCE = 'all'
```

```bash
# forget everything, keep the converted binaries
GLIDER=selkie python -c "import config; config.clear_outputs()"
# also throw away the binary conversion (slow to redo)
GLIDER=selkie python -c "import config; config.clear_outputs(rawnc=True)"
# just show what has been done
GLIDER=selkie python -c "import config; config.status()"
```

## New data from the same glider

Drop the new folder into `data/` and rerun. `01` converts every download
folder it finds for that glider — downloads are not always cumulative, so
using only the newest one would silently drop older segments.

To restrict it, set `DATA_DIRS` at the top of `01_process_to_nc.py`.

## Choosing legs (segments)

Slocum file names carry the segment number: `selkie-2026-197-3-43.tbd` is
segment **43** of mission 3. `01` writes one netcdf per segment, and
`config.segment_table()` turns those into a segment → time range lookup,
cached in `.state/<glider>/segments.csv`.

In `04_interactive_html.py`:

```python
SEGMENTS = 43         # just segment 43
SEGMENTS = (40, 43)   # segments 40 to 43
SEGMENTS = -10        # the last 10 segments
SEGMENTS = None       # everything
```

Rebuild the table if it looks stale:
`GLIDER=selkie python -c "import config; config.segment_table(rebuild=True)"`

## The interactive page (04)

Five tabs:

- **Sections** — contour depth-vs-time panels on a uniform time axis, in
  cmocean colours, with a colour-scheme dropdown. Dashed grey vertical lines
  mark the profiles that were really measured; everything between them is
  interpolated, and gaps longer than `MAX_GAP_HOURS` stay blank.
- **Science** — scatter with dropdowns for x, y, colour and colour scheme,
  plus a T-S diagram with potential-density isolines. `+ glider depth`
  overlays the dive profile on the scatter itself.
- **Glider** — the same for the engineering variables.
- **3D** — the multibeam bathymetry as terrain, with the section hung along
  the track as a curtain. Unmeasured parts are transparent. Slider picks the
  time window.
- **Map** — bathymetry image + island outline + track through the
  surfacings, coloured by time + red arrows for the depth-averaged current
  over each surface-to-surface interval, and a **current rose** sub-tab.

### Keeping the file small

Every dropdown option embeds its own copy of the data, so the page grows
fast. The levers, biggest first:

| setting | effect |
|---|---|
| `SECTION_DEPTH_STRIDE` | keep every Nth depth bin. A 340 px panel cannot draw 1100 rows; 4 is visually identical and 4× smaller. **The biggest one.** |
| `SECTION_MAX_COLS` | hard cap on time columns per panel |
| `SECTION_DECIMALS` | JSON stores numbers as text; every decimal is a character |
| `N_TIME_WINDOWS` | each 3D slider step stores a full copy of the curtain |
| `MAX_POINTS` | samples kept for the scatter tabs |
| size of `bathymetry_PE500.png` | base64-embedded once per page |

Run `06_html_weight.py` to see where the megabytes actually are before
cutting anything.

## Notes

- **Salinity and density are computed by the plotting scripts**, not read
  from the file. pyglider needs conductivity, temperature and pressure at the
  same instant, which the decimated realtime feed rarely gives, so its
  salinity comes out nearly empty. `02`/`04` compute it on the grid with
  `gsw`, using the depth axis as pressure (dbar ≈ m). For the recovered
  full-resolution dataset prefer pyglider's own salinity plus its
  [CTD adjustment](https://pyglider.readthedocs.io/en/latest/adjust_CTD.html).
- **Fewer points than expected?** Postprocessing cannot add samples. The
  realtime feed is decimated and, depending on the science configuration, may
  only sample on downcasts. The full record is in the `dbd`/`ebd` files after
  recovery — set `REALTIME = False` (or `REALTIME=0` in the environment) and
  rerun.
- **Depth-averaged currents** are one estimate per dive, not a time series.
  `m_water_vx/vy` is what the glider computes between surfacings, so the map
  and rose average it over each surface-to-surface interval and draw one
  arrow per interval. `CURRENT_SKIP_FIRST` drops the early dives, where the
  estimate is unreliable.
- Files `01` generates for its own use (`.state/<glider>/sensor_list_used.txt`,
  `deployment_used.yml`) are safe to delete. Your `deployment_<glider>.yml`
  is never modified.
- Everything derived is gitignored, including `.state/` — it holds absolute
  paths from the machine that produced it, so a clone that inherited it would
  believe work was done that has no files behind it.