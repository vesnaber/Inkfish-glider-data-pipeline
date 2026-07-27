# Slocum glider data pipeline

This repository is used for processing Slocum glider outputs and log files, primarily applied for operational use. You can process the *.tbd and *.sbd data, as well as all the log files (communicaiton with the glider) directly from glider while piloting it. It works for multiple gliders at the same time. The main resulting tool is the **interactive HTML site** where you can visualize various parameters and quickly see whether the gliders have any warnings and errors. Moreover, you can project the battery usage and plan an optimal recovery date. 

Main processing (raw --> nc files) is done using [pyglider](https://pyglider.readthedocs.io).

**Multiple gliders can be processed and plotted at the same time. Every output folder has one subfolder per glider, and the glider names are defined by their `deployment_<glider_name>.yml` file name in the repo root. That filename is the glider name, and it must also match metadata (glider_name) inside the yml and the prefix of the binary filenames. So if you have multiple `deployment_<glider_name>.yml` files, you can process this many of the gliders.**

Files in the repository:
```
config.py                     <- definition of all paths (there can be different locaiton where data is stored whether you are working locally or on a irtual machine)
fresh_start.py                <- run this first. This script makes all the missing folders and checks the setup (whether you have the correct python packages installed in your kernel/venv)
deployment_<glider>.yml       <- metadata + sensor variables definiton for creating nc files (check and write it up at the very beginning of deployment)
sensor_list_<glider>.txt      <- this file gets created/re-written by 00 script, do not edit it by hand (!)
run_gliders.py                <- this is the main script that runs all necessary scripts for every glider (by default it runs for every gldier)

00_build_sensor_list.py.      <- these scripts are described below
01_process_to_nc.py
02_plots_full_timeseries.py
03_process_glider_logs.py
03b_battery_status.py  
04_interactive_html.py
05_interactive_html_merge_gliders.py

cache/<glider>/               \
rawnc/<glider>/segments/       |  this files are not in the github repository, but they get created automatically
rawnc/<glider>/merged/         |  (all gitignored)
L0-timeseries/<glider>/        |
L0-profiles/<glider>/          |
L0-gridfiles/<glider>/         |
L0-logs/<glider>/              |
plots/<glider>/                |
interactive/<glider>/          |
.state/<glider>/              /   <- this folder tracks what has already been processed (to avoid re-processign the same segments)
```

## Do you work on local computer or on virtual machine? Set it up accordingly:


Currently in `config.py` we define two different locations where the data is stored (current configuration in RV Hydra): 
- when you work on your local computer and you download the data files and log files from [SFMC website](https://sfmc.webbresearch.com/), you need to insert the data files in folder: `<repo>/data/<glider>-from-glider/` and log files in the folder: `<repo>/data/<glider>-logs/`
- currently when you work on RV Hydra virtual machine enviroment (i.e. VM), the idea is that your data is automatically being downloaded (near-real-time) to folder `~/data/rt-data/<glider>/from-glider/`. In order for this to work properly, you need to set up a few things in VM t the beginning of the new deployment. 

Besides setting up the correct folders where the data is stored, you also should know (and define) what kind of data you have. There ar two types of dataset that glider produces: 
- **realtime** data is stored as`sbd`/`tbd` files: these are confined files that contain information about science and glider flight per segment. They are small (as small as you decide them to be) and show measuring variables at every X seconds. It is advised that the gliders are set to download these files every time the glider has a connection with you/the satellite (when the glider is on the surface)
- **recovered** data is stored as `dbd`/`ebd` files: these are files that contain the full timeseries from the glider. These are large fiels and usually they are downloaded from the glider at the very end (when the glider is back on board).

Anothen thing to check is: how do the scritp know whether your setup is local computer or VM. By default, it is set automatically (the script first check whether you have any files in data/from-glider<glider>, and if not, checks whether there are folders and files as they should be in VM), but to have more control over this (and in case you have data in both folders), it is more rubust to set this up manually in `config.py` script. This can be done by changing the variables MACHINE and DATATYPE:
```python
MACHINE  = 'auto'      # 'local' | 'vm'          | 'auto' (set it up based on your workflow)
DATATYPE = 'auto'      # 'realtime' | 'recovered' | 'auto' (set it up based on whether you want to process sbd/tbd files (=realtime) or dbd/ebd files (=recovered)
```

Summary: 
| switch | what it decides | values |
|---|---|---|
| `MACHINE` | where the **data folders** are | `local` = `<repo>/data/<glider>-from-glider/`  •  `vm` = `~/data/rt-data/<glider>/from-glider/` |
| `DATATYPE` | which **binaries** to read | `realtime` = `sbd`/`tbd`  •  `recovered` = `dbd`/`ebd` |

`'auto'` works it out from the data on disk: location decides `MACHINE`,
file extension decides `DATATYPE`.

Environment variables override both, per axis, so `run_gliders.py` and the VM
keep working no matter how the file is pinned:

| env var | overrides | values |
|---|---|---|
| `GLIDER` | which glider | `selkie`, `unit_1272`, … |
| `DATA_LAYOUT` | `MACHINE` | `local`, `vm` |
| `REALTIME` | `DATATYPE` | `1` (realtime), `0` (recovered) |
| `GLIDER_DATA_ROOT` | the data root | any path |

**Outputs always stay in the repo**, in both layouts — only the *input*
location moves.

Check what actually resolved before a long run:

```bash
python config.py            # prints mode + layout, each with its reason
```

## Running from a terminal

`run_gliders.py` runs the whole chain (00 → 01 → 03 → 03b → 04 → 05) for one
or more gliders, one subprocess each, streaming output and writing
`logs/<glider>_<timestamp>.log`.

**1. Home (local) + realtime**

```bash
python run_gliders.py -r 1 --layout local
```

**2. Home (local) + recovered**

```bash
python run_gliders.py -r 0 --layout local
```

**3. VM + realtime** — the normal VM case, and the defaults

```bash
python run_gliders.py
# explicit equivalent:
python run_gliders.py -r 1 --layout vm
```

**4. VM + recovered**

```bash
python run_gliders.py -r 0 --layout vm --data-root ~/data/<recovered-folder>
```

`--layout vm` alone points at `~/data/rt-data`, which holds the *stream*.
Recovered `dbd`/`ebd` live somewhere else, so pass `--data-root`.
GUESSING!! at where recovered data gets staged on the VM — set it to
whatever is true.

**5. One script, or one glider, in any configuration**

```bash
python run_gliders.py -g selkie --only 01              # one glider, one step
python run_gliders.py -g selkie unit_1272 --only 04 05 # two gliders, the html
python run_gliders.py --skip 01                        # all but the slow one
python run_gliders.py -j 1                             # sequential, readable log
python run_gliders.py --list                           # preview, run nothing
```

`--only` / `--skip` match on any part of the filename, so `04`,
`interactive` and `04_interactive_html.py` all work. Combine freely with
`-r` / `--layout`.

Or call a script directly — simplest when debugging, since the environment
is right there in the command:

```bash
GLIDER=selkie REALTIME=0 DATA_LAYOUT=local python 01_process_to_nc.py
```

**6. Only the plots (02)**

```bash
GLIDER=selkie REALTIME=1 DATA_LAYOUT=local python 02_plots_full_timeseries.py
```

`02` is deliberately **not** in `run_gliders.py`'s `SCRIPTS` list, so
`--only 02` fails with "matched nothing". Run it directly, or add it to that
list.

**Housekeeping, any configuration**

```bash
GLIDER=selkie python -c "import config; config.status()"           # what's done
GLIDER=selkie python -c "import config; config.clear_outputs()"    # forget L0, keep the conversion
GLIDER=selkie python -c "import config; config.clear_outputs(rawnc=True)"  # also redo the slow step
```

## Fresh start

After cloning:

```bash
conda create -n gliderwork python=3.12
conda activate gliderwork
conda install -c conda-forge pyglider dbdreader cmocean gsw plotly pyshp netcdf4 pyarrow

python fresh_start.py
```

`fresh_start.py` asks `config` where things are, so it reports the *real*
inbox for the machine it runs on. It prints flight vs science file counts
separately, how many files survive the filter, and whether the sensor cache
is present. It changes nothing that already exists.

It will tell you to do these, in order:

1. **Write `deployment_<glider>.yml`.** Copy the example, rename it, set the
   `metadata:` block (`glider_name` must match the file name) and, under
   `netcdf_variables:`, each entry's `source:` = the Slocum sensor name.
   You do *not* have to remove sensors your glider lacks — `01` skips them
   with a warning.
2. **Set `deployment_start:` under `metadata:`.** Everything before that
   date is ignored (see below). Without it, old missions still sitting in
   the folder get processed too.
3. **Put the binaries in the inbox** — one folder, no timestamp:
   `data/<glider>-from-glider/` locally, or
   `~/data/rt-data/<glider>/from-glider/` on the VM. New downloads just add
   to it; already-converted files are skipped.
4. **Optional, for the map and 3D tabs:** an ASCII grid in
   `data/bathymetry_xyz/` and an image plus a `.bounds` sidecar in
   `data/bathymetry_image/`. Both tabs work without them, just plainer.
5. Rerun `python fresh_start.py` until it is happy.

| script | what it does |
|---|---|
| `00_build_sensor_list.py` | Looks inside the binaries, writes `sensor_list_<glider>.txt` with only the sensors that actually carry measurements. Needed once per glider. |
| `01_process_to_nc.py` | Binaries → netcdf. **Incremental** — see below. |
| `02_plots_full_timeseries.py` | Static figures for the whole deployment. The first cell holds everything worth changing. |
| `03_process_glider_logs.py` | Parses the surface dialogs into `L0-logs/<glider>/`. |
| `03b_battery_status.py` | Battery trend from the parsed logs. |
| `04_interactive_html.py` | `interactive/<glider>/<glider>.html` — a normal file, no server. |
| `05_interactive_html_merge_gliders.py` | `interactive/all_gliders.html` — a button per glider, each page loaded on first click. |
| `diagnose_binaries.py` | Reads a binary's header, works out which `.cac` it needs, and says whether it is there. Use when a file type refuses to convert. |

## Which files get picked up

Only binaries named `<glider>-YYYY-DDD-M-S.<ext>` (or with `_` as separator)
are converted, and only when the mission date in the name is on or after
`deployment_start:` in the yml. Everything else — other gliders, 8.3 DOS
names, older missions — is excluded and reported once per folder.

pyglider converts *every* binary in the directory it is handed, so filtering
the list is not enough: `01` symlinks the accepted files into
`.state/<glider>/staged/` and points pyglider at that instead.

If a dataset ever arrives with 8.3 names (straight off the glider flash):

```bash
GLIDER_FILE_FILTER=0 python 01_process_to_nc.py
```

## Incremental processing

`01` fingerprints each stage in `.state/<glider>/` and skips work it has
already done, so a rerun after a new download only costs the new segments.

- **rawnc/segments/** is an archive: converted binaries are only ever added.
  Rebuilt only if the sensor list, the yml, the mode, or `deployment_start`
  changed.
- The merge runs on a throwaway copy, because pyglider's `merge_rawnc`
  consumes its input directory. Empty segments are dropped from the copy —
  the archive keeps them.
- timeseries, profiles and grid are rewritten, but only when something
  upstream actually moved. Each is deleted just before it is rewritten, so a
  stale or still-open file cannot block the write.

Each stage prints why it ran: `never run`, `settings or upstream changed`,
`output missing`, or `up to date`. `TIMING = True` prints seconds per stage.

To redo something, in `01`:

```python
FORCE = 'timeseries'   # that stage and everything after it
FORCE = 'all'
```

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
  Above the map, **pick a time period** and the surfacings inside it light up
  in orange, with a count — that is how you find *where* the glider was when
  something odd shows up in the data. `last 24 h` / `last 3 d` are shortcuts.

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
| size of the bathymetry image | base64-embedded once per page |

## When something breaks

| symptom | cause | fix |
|---|---|---|
| `no *.sbd files for "<glider>"` and the path looks wrong | wrong layout | `python config.py` to see what resolved; set `MACHINE`, or pass `DATA_LAYOUT=` |
| Plots empty, `01` produced nothing | mode/suffix mismatch — looking for `dbd/ebd` when you have `sbd/tbd` | set `DATATYPE`, or `REALTIME=1` |
| `NOT ONE *.tbd converted` | that file type's `.cac` sensor cache is missing (flight and science have different ones) | `GLIDER=<g> python diagnose_binaries.py`, then `COPY=1` to copy what it finds |
| `OSError: no files to open` in the merge | same thing, one stage later | as above |
| `ValueError: Cannot handle size zero dimensions` | empty segments | handled — `01` drops them from the merge copy |
| `Segmentation fault` in the merge | non-threadsafe HDF5 in a pip venv + `lock=False` | handled — `01` forces dask's synchronous scheduler |
| `PermissionError: [Errno 13]` writing an L0 file | the file is still open in a VS Code/Jupyter kernel | handled — `01` unlinks first; restarting the kernel also fixes it |
| Only one day / no isopycnals in `02` | one profile in the gridfile, not a plotting bug | `GLIDER=<g> python inspect_L0.py` says which stage lost the data |

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
  recovery — switch `DATATYPE` to `'recovered'` (or `REALTIME=0`) and rerun.
- **Depth-averaged currents** are one estimate per dive, not a time series.
  `m_water_vx/vy` is what the glider computes between surfacings, so the map
  and rose average it over each surface-to-surface interval and draw one
  arrow per interval. `CURRENT_SKIP_FIRST` drops the early dives, where the
  estimate is unreliable.
- Files `01` generates for its own use (`.state/<glider>/sensor_list_used.txt`,
  `deployment_used.yml`, `staged/`) are safe to delete. Your
  `deployment_<glider>.yml` is never modified.
- Everything derived is gitignored, including `.state/` — it holds absolute
  paths from the machine that produced it, so a clone that inherited it would
  believe work was done that has no files behind it.