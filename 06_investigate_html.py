'''
06_html_weight.py
Where do the megabytes go? Builds each tab for one glider and reports the
JSON size of every figure, split into traces vs dropdown/slider menus, so
you can see what is worth cutting before cutting anything.

    python 06_html_weight.py
'''
#%% ---------------- settings ----------------
import config

TOP_TRACES = 6      # how many of the biggest traces to list per figure

#%% ---------------- load 04 as a module ----------------
import importlib.util
import json
from pathlib import Path
import plotly.io as pio

spec = importlib.util.spec_from_file_location(
    'viz', config.ROOT / '04_interactive_html.py')
viz = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viz)          # needs the __main__ guard in 04

#%% ---------------- build every figure once ----------------
t0, t1 = viz.segment_window()
grid = viz.load_grid(config.GLIDER, t0, t1)
ts = viz.load_ts(config.GLIDER, t0, t1)
terrain = (viz.load_bathy_terrain(bbox=viz.track_bbox(ts))
           if viz.SHOW_TERRAIN else None)

figs = {
    'Sections':        viz.sections_fig(grid),
    'Science scatter': viz.scatter_fig(ts, viz.SCIENCE_VARS,
                                       viz.DEFAULT_SCIENCE, ''),
    'T-S diagram':     viz.ts_fig(ts),
    'Glider scatter':  viz.scatter_fig(ts, viz.GLIDER_VARS,
                                       viz.DEFAULT_GLIDER, ''),
    '3D curtain':      viz.curtain_fig(grid, ts, terrain),
    'Map':             viz.map_fig(ts, viz.coastline_geojson(viz.COASTLINE_SHP),
                                   viz.bathy_layer()),
}

#%% ---------------- weigh them ----------------
MB = 1e6

def weigh(name, fig):
    if fig is None:
        return None
    d = json.loads(pio.to_json(fig))
    lay = d.get('layout', {})
    traces = d.get('data', [])

    n_tr = len(json.dumps(traces))
    n_menu = len(json.dumps(lay.get('updatemenus', [])))
    n_slide = len(json.dumps(lay.get('sliders', [])))
    n_layers = len(json.dumps(lay.get('map', {}).get('layers', [])))
    n_lay = len(json.dumps(lay))
    total = n_tr + n_lay

    big = sorted(((len(json.dumps(t)), t.get('type', '?'),
                   t.get('name', '') or f"#{i}")
                  for i, t in enumerate(traces)), reverse=True)

    return dict(name=name, total=total, traces=n_tr, menus=n_menu,
                sliders=n_slide, layers=n_layers,
                other=n_lay - n_menu - n_slide - n_layers,
                n=len(traces), big=big)


rows = [r for r in (weigh(k, v) for k, v in figs.items()) if r]
rows.sort(key=lambda r: -r['total'])
grand = sum(r['total'] for r in rows)

print(f'\n=== {config.GLIDER} ===')
print(f'{"figure":18s} {"total":>8s} {"traces":>8s} {"menus":>8s} '
      f'{"sliders":>8s} {"img":>8s} {"other":>8s}   share')
for r in rows:
    print(f'{r["name"]:18s} {r["total"]/MB:7.1f} {r["traces"]/MB:8.1f} '
          f'{r["menus"]/MB:8.1f} {r["sliders"]/MB:8.1f} '
          f'{r["layers"]/MB:8.1f} {r["other"]/MB:8.1f}   '
          f'{100*r["total"]/grand:4.0f} %')
print(f'{"TOTAL":18s} {grand/MB:7.1f} MB  (plus ~35% for the html/base64 wrapper)')

print('\nbiggest traces per figure:')
for r in rows:
    print(f'  {r["name"]}  ({r["n"]} traces)')
    for size, typ, nm in r['big'][:TOP_TRACES]:
        print(f'    {size/MB:6.2f} MB  {typ:12s} {nm}')

print('\nreminder: "menus" and "sliders" are DUPLICATED DATA - every dropdown '
      'option stores its own full copy of the array it would swap in.')

# %%