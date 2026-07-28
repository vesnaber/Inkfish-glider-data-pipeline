# Slocum glider data pipeline

This repository is used for processing Slocum glider outputs and log files, primarily applied for operational use. You can process the *.tbd and *.sbd data, as well as all the log files (communicaiton with the glider) directly from glider while piloting it. It works for multiple gliders at the same time. The main resulting tool is the **interactive HTML site** where you can visualize various parameters and quickly see whether the gliders have any warnings and errors. Moreover, you can project the battery usage and plan an optimal recovery date. 

Main processing (raw --> nc files) is done using [pyglider](https://pyglider.readthedocs.io).

**Multiple gliders can be processed and plotted at the same time. Every output folder has one subfolder per glider, and the glider names are defined by their `deployment_<glider_name>.yml` file name in the repo root. That filename is the glider name, and it must also match metadata (glider_name) inside the yml and the prefix of the binary filenames. So, if you have multiple `deployment_<glider_name>.yml` files, you can process multiple gliders at the same time.**

Files in the repository:
```
config.py                     <- definition of all paths and dependancies
fresh_start.py                <- run this first. This script makes all the missing folders and checks the setup (whether you have the correct python packages installed in your kernel/venv)
deployment_<glider>.yml       <- metadata + sensor variables definiton for creating nc files (check and write it up at the very beginning of deployment)
sensor_list_<glider>.txt      <- this file gets created/re-written by 00 script, do not edit it by hand (!)
run_gliders.py                <- this is the main script that runs all necessary scripts for every glider (by default it runs for every gldier)

00_build_sensor_list.py.      <- the numbered scripts are described below
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

## How to start?

First, clone this repository on your local computer or virtual machine. After cloning install all the necessary python packages. If you are using conda, follow these steps:

```bash
conda create -n gliderwork python=3.12
conda activate gliderwork
conda install -c conda-forge pyglider dbdreader cmocean gsw plotly pyshp netcdf4 pyarrow
```

The very first script you need to run is: 

```bash
python fresh_start.py
```

With running the `fresh_start.py` script, you go through `config.py` file, check the `.yml` files and check if you have all necessary python packages installed. The script prints the amount of existing 
flight and science files (if any), and whether you have cache files. It also creates the missing folders that are needed to follow the pipeline.

Follow orders of `fresh_start.py` and set up the missing files and variables. The most important steps to follow are:

1. **Write a new `deployment_<glider>.yml`.** Copy the example, rename it, set the
   `metadata:` block (`glider_name` must match the file name) with correct starting date of your deployment and your personal informaiton, under
   `netcdf_variables:`, each entry's `source:` = the Slocum sensor name.
   You do *not* have to remove sensors your glider lacks — `01` skips them
   with a warning. Make sure you do not leave any parts of `metadata` empty!
   **Specifically focus on setting `deployment_start:` correctly.** Without it, old missions still sitting in
   the data folder get processed too and the plots might look messy.
   **If you have multiple gliders at the same time, make `.yml` file for each glider separately!!**
2. **Download the cache files from [SFMC website](https://sfmc.webbresearch.com/)**: You need to download cache files 
that are specific to your gliders. Place them in folder: `cache/<glider_name>` for each glider separately. Rather have more cache files then too little. 
3. **Put the glider binaries in the right folders**: for each glider, download the data from [SFMC website](https://sfmc.webbresearch.com/) that can be found under the buttom from-glider and store it: 
- if working on local computer: `data/<glider>-from-glider/` 
- if workin on VM: `~/data/rt-data/<glider>/from-glider/`
- if you store it somewhere else, make sure you change the `config.py` file to specify the correct folder
4. **Put the glider logs in the right folders**: for each glider, download the logs from [SFMC website](https://sfmc.webbresearch.com/) that can be found under the buttom logs and store it: 
- if working on local computer: `data/<glider>-logs/` 
- if workin on VM: `~/data/rt-data/<glider>/logs/`
- if you store it somewhere else, make sure you change the `config.py` file to specify the correct folder
5. **Optional: to create maps with bathyemtry:** an ASCII grid in
   `data/bathymetry_xyz/` and an image of a bathyemtry together with longitude and latitude bounds `.bounds` file in
   `data/bathymetry_image/`.
6. Rerun `python fresh_start.py` to check if you are still missing something.


## Running scripts from a terminal

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

The quickest and easiest way to run the scripts is to run them all at the same time with `run_gliders.py` script as:

```bash
python run_gliders.py            # prints out your configuration for the default glider
```
This script runs the entire chain (00 → 01 → 03 → 03b → 04 → 05) for as many gliders as you have `.yml` files. The log of this run is saved as: `logs/<glider>_<timestamp>.log`.

## Are you working on a local computer or on virtual machine? Set it up accordingly:

Currently in `config.py` we define two different locations where the data is stored (current configuration in RV Hydra): 
- when you work on your local computer and you download the data files and log files from [SFMC website](https://sfmc.webbresearch.com/), you need to insert the data files in folder: `<repo>/data/<glider>-from-glider/`, and log files in the folder: `<repo>/data/<glider>-logs/`
- currently (July 2026), when you are work on RV Hydra virtual machine enviroment (i.e. VM), the idea is that your data is automatically being downloaded (near-real-time) to folder `~/data/rt-data/<glider>/from-glider/`. In order for this to work properly, **you need to set up a few things in VM at the beginning of the new deployment.** 

Furthermore, you also should know (and define) what kind of data you have and want to process. There are two types of dataset that glider produces: 
- **realtime** data is stored as`sbd`/`tbd` files: these are confined files that contain information about science and glider flight per segment. They are small (as small as you decide them to be) and show measured variables at every X seconds. It is advised that the gliders are set to download these files every time the glider has a connection with you/the satellite (when the glider is at the surface).
- **recovered** data is stored as `dbd`/`ebd` files: these are files that contain the full timeseries from the glider. These are large fiels and usually they are downloaded from the glider at the very end (when the glider is retreived and back on board).

Once you know your confiuration and what data you want to process, you need to define that in the scripts. So, how do the scrits know whether your setup is local computer or VM? 
- By default, your configuraiton is detected automatically (the scripts first check whether you have any files in `data/from-glider<glider>`, and if not, they check whether you have existing folders and files as they should be set in VM).
- **However,** it is advised that your set up has more control over this matter (and in case you have data in both folders). The workflow becomes more rubust if you set up your configuration manually in `config.py` script. This can be done simply by changing the following two variables `MACHINE` and `DATATYPE` as:
```python
MACHINE  = 'auto'      # set it up insted to: 'local' | 'vm' | 'auto' (set it up based on your workflow)
DATATYPE = 'auto'      # set it up insted to: 'realtime' | 'recovered' | 'auto' (set it up based on whether you want to process sbd/tbd files (=realtime) or dbd/ebd files (=recovered)
```

Summary: 
| variable | what is it | possible values values |
|---|---|---|
| `MACHINE` | where the **data folders** are | `local` = `<repo>/data/<glider>-from-glider/`  •  `vm` = `~/data/rt-data/<glider>/from-glider/` |
| `DATATYPE` | which **binaries** to read | `realtime` = `sbd`/`tbd`  •  `recovered` = `dbd`/`ebd` |


It is also possible to override these variables by running the script via the Terminal witht he followign environemntal variables:

| env var | overrides | values |
|---|---|---|
| `GLIDER` | which glider | `selkie`, `unit_1272`, … |
| `DATA_LAYOUT` | `MACHINE` | `local`, `vm` |
| `REALTIME` | `DATATYPE` | `1` (realtime), `0` (recovered) |
| `GLIDER_DATA_ROOT` | the data root | any path |

You can use this as:
```bash
GLIDER=selkie python <script_you_want_to_run>.py               # run this script for selkie glider only
DATA_LAYOUT=local python <script_you_want_to_run>.py           # run this script on your lcoal computer
GLIDER=selkie REALTIME=1 python <script_you_want_to_run>.py    # run this script if you want to process the sbd/tbd files from selkie
```

Or another way:
```bash
python run_gliders.py -g selkie --only 01              # one glider, one step
python run_gliders.py -g selkie unit_1272 --only 04 05 # two gliders, the html
python run_gliders.py --skip 01                        # all but the slow one
python run_gliders.py -j 1                             # sequential, readable log
python run_gliders.py --list                           # preview, run nothing
```

If you want to check your configuration, run this in Terminal:

```bash
python config.py            # prints out your configuration for the default glider
```


## Run fils with recovered data (not yet tested):

```bash
python run_gliders.py -r 0 --layout local --data-root /data/<recovered-folder>
```

## Housekeeping

In order to not re-process the segments that are already processed, the code creates .status folder where you store the informaiton about what has already been processed and what not. This saves some time in processing the data and creating the interactive html whenever you have new data available. 

You can check the status and, if needed, clear the status:
```bash
GLIDER=selkie python -c "import config; config.status()"           # what's done
GLIDER=selkie python -c "import config; config.clear_outputs()"    # forget L0, keep the conversion
GLIDER=selkie python -c "import config; config.clear_outputs(rawnc=True)"  # also redo the slow step
```

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
- THIS NEEDS TO BE UPDATED

## Troubleshooting: 

- **missing cache**: check if you have all needed caches from [SFMC website](https://sfmc.webbresearch.com/). If you are missing any of them, the processing will not work. Make sure you download them all. It is better to have too many than too little of them. 
- **cache incorrect**: sometimes cache gets saves as `.CAC` instead of `.cac`. In that case manually change the name of the cache file to be `.cac`. 
- **change of settings**: you have new settings, but .status remembered the old one. In that case delete the .status folder and re-run everything.
- **wroge mode**: you are running in `recovered` mode, while your data is `sbd`/`tbd`. In that case check your `config.py` file or override the scripts with `REALTIME=1` or `-r 1` (see above) when running in Terminal.



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
- **Depth-averaged currents** are one estimate per dive, not a time series.
  `m_water_vx/vy` is what the glider computes between surfacings, so the map
  and rose average it over each surface-to-surface interval and draw one
  arrow per interval.