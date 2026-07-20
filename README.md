# Slocum glider data pipeline

Turns Slocum glider binaries into netcdf and plots, using
[pyglider](https://pyglider.readthedocs.io).

```
config.py                    <- SET YOUR GLIDER HERE (the only file you must edit)
deployment_{your_glider_name}.yml               <- metadata + which sensor maps to which variable
sensor_list.txt              <- written by 00, don't edit by hand
data/<download folder>/      <- put glider files here (sbd/tbd or dbd/ebd)
L0-timeseries/               \
L0-profiles/                  } created by 01
L0-gridfiles/                /
plots/                       <- all figures
interactive/                 <- here the HTML links are stored for interctive website
```

## Install

```bash
conda create -n gliderwork python=3.12
conda activate gliderwork
conda install -c conda-forge pyglider dbdreader cmocean gsw
```

## First time with a new glider

1. Copy the download folder from the dockserver into `data/`.
   Keep the folder name as it comes (it ends in a timestamp) — the scripts
   pick the newest one automatically.
2. Open **`config.py`** and set:
   - `GLIDER` — the glider name, e.g. `'selkie'` or `'unit_1272'`
   - `REALTIME` — `True` for the live feed (`sbd`/`tbd`),
     `False` for the full-resolution data you get after recovery (`dbd`/`ebd`)
3. Open **`deployment_{your_glider_name}.yml`** and set the `metadata:` block
   (`glider_name` must match `config.GLIDER`, plus serial, project, etc.).
   Under `netcdf_variables:` each entry needs a `source:` = the Slocum sensor
   name. You don't have to remove sensors your glider lacks — step 1 skips
   them for you.
4. Run the steps below.

## Running

```bash
python 00_build_sensor_list.py       # which sensors actually have data
python 01_process_to_nc.py           # binaries -> netcdf + quick look plot
python 02_plots_full_timeseries.py   # proper plots, whole deployment
python 04_interactive_html.py        # interactive web page (zoom, pick axes, map)
```

All four also run cell-by-cell in VS Code / Jupyter (`#%%` markers).

**00** looks inside the binaries and writes `sensor_list.txt` with only the
sensors that actually carry measurements. It prints what `deployment.yml`
asked for but couldn't find.

**01** reads the newest folder in `data/`, drops anything missing (with a
warning — it does not crash), and writes the timeseries, profiles and grid.
Old netcdf files are deleted first, so you can never plot a stale file.
A quick look figure lands in `plots/preliminary_data.png`.

**02 / 03** make the real figures. The first cell of each holds everything
worth changing: time window (02) or number of legs (03), which variables go
in which figure, colour range, figure size.

## New data from the same glider

Drop the new folder into `data/` and rerun `01`, `02`, `03`. Nothing else
changes. To process an older download instead, set `DATA_DIR` at the top
of `01_process_to_nc.py`.

## Notes

- **Salinity and density are computed by the plotting scripts**, not taken
  from the file. pyglider needs conductivity, temperature and pressure at the
  same instant, which the decimated realtime feed almost never gives, so its
  salinity comes out nearly empty. `02`/`03` compute it on the grid with `gsw`,
  using the depth axis as pressure (dbar ≈ m). For the recovered
  full-resolution dataset, prefer pyglider's own salinity plus its
  [CTD adjustment](https://pyglider.readthedocs.io/en/latest/adjust_CTD.html).
- **Fewer points than expected?** Postprocessing can't add samples. The
  realtime feed is decimated and, depending on the glider's science
  configuration, may only sample on downcasts. The complete record is in the
  `dbd`/`ebd` files after recovery — set `REALTIME = False` and rerun.
- Files that step 01 generates for its own use (`sensor_list_used.txt`,
  `deployment_used.yml`) are safe to delete; your `deployment.yml` is never
  modified.
- Suggested `.gitignore`: `data/ cache/ rawnc/ L0-* plots/ *.nc
  sensor_list_used.txt deployment_used.yml`

## Choosing legs (segments)

Slocum file names carry the segment number: `selkie-2026-197-3-43.tbd` is
segment **43** of mission 3. Step 01 writes one netcdf per segment into
`rawnc/`, and `config.segment_table()` turns those into a lookup of
segment → time range, cached in `segments.csv`.

In `03_plots_lastNlegs.py` and `04_interactive_html.py` set:

```python
SEGMENTS = 43         # just segment 43
SEGMENTS = (40, 43)   # segments 40 to 43
SEGMENTS = -10        # the last 10 segments
SEGMENTS = None       # everything
```

If the table looks out of date after new data: `python -c "import config;
config.segment_table(rebuild=True)"`.

## Interactive page (04)

Makes `plots/interactive/<glider>.html` — a normal file, no server. Five tabs:

- **Sections** — the same interpolated depth-vs-time colour plots as 02/03,
  in cmocean colours, with a **colour-scheme dropdown** (per-variable cmocean,
  or force one map: thermal, haline, dense, deep, balance, Viridis, …)
- **Science** / **Glider** — scatter with dropdowns for x, y, colour and
  colour scheme
- **3D** — the section hung along the track as a curtain: each profile is a
  column and the field is interpolated between them. Dropdowns for variable
  and colour scheme. Falls back to coloured points if the grid has no position
- **Map** — `data/bathymetry_PE500.png` laid over the basemap (corner
  coordinates in `BATHY_BOUNDS`), the island outline from
  `data/cuw_adm0/CUW_adm0.shp`, the track, and the **last position in red**

The header shows the segments plotted, the **time of the last measurement**,
and when the page was built. List several gliders in `GLIDERS` for one page
each, linked at the top.

Handy settings: `MARKER_SIZE`, `CMAP_PER_VAR`, `COLOUR_SCHEMES`, `CLIM_PCT`,
`FILL_GAPS` / `MAX_GAP_HOURS` (interpolation), `MAP_STYLE`, `MAX_POINTS`
(every dropdown option embeds its own copy of the data, so this controls file
size — 20 000 points ≈ 8 MB).

```bash
conda install -c conda-forge plotly cmocean gsw pyshp
```
