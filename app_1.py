import requests
import xml.etree.ElementTree as ET
import datetime
import geopandas as gpd
import folium
import osmnx as ox
import pandas as pd

from branca.colormap import linear
from shapely.geometry import box
from folium.plugins import TreeLayerControl
from datetime import datetime, timezone, timedelta

# ============================================================
# CONFIG
# ============================================================

API_KEY = "1d9d451c-28be-4deb-b051-9bd521a062db"

MIN_LON = 23.70
MIN_LAT = 61.48
MAX_LON = 23.80
MAX_LAT = 61.52

BBOX = f"{MIN_LON},{MIN_LAT},{MAX_LON},{MAX_LAT}"

# ============================================================
# CREATE MAP
# ============================================================

center_lat = (MIN_LAT + MAX_LAT) / 2
center_lon = (MIN_LON + MAX_LON) / 2

mymap = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=12,
    tiles="OpenStreetMap"
)

# ============================================================
# DOWNLOAD ELEVATION CONTOURS
# ============================================================

url = (
    "https://avoin-paikkatieto.maanmittauslaitos.fi/"
    "maastotiedot/features/v1/"
    "collections/korkeuskayra/items"
)

response = requests.get(
    url,
    params={
        "bbox": BBOX,
        "limit": 10000,
        "f": "json",
        "api-key": API_KEY
    },
    timeout=60
)

response.raise_for_status()

data = response.json()

# ============================================================
# LOAD CONTOURS
# ============================================================

gdf = gpd.GeoDataFrame.from_features(data["features"])

elevation_col = "korkeusarvo"

gdf = gdf[gdf[elevation_col].notna()]

gdf = gdf.set_crs(epsg=4326, allow_override=True)

# ============================================================
# ELEVATION COLOR SCALE
# ============================================================

min_elev = gdf[elevation_col].min()
max_elev = gdf[elevation_col].max()

elev_colormap = linear.YlGnBu_09.scale(
    min_elev,
    max_elev
)

# ============================================================
# ELEVATION STYLE
# ============================================================

def elevation_style(feature):

    elev = feature["properties"][elevation_col]

    return {
        "color": elev_colormap(elev),
        "weight": 2,
        "opacity": 0.8
    }

# ============================================================
# ELEVATION LAYER
# ============================================================

contour_layer = folium.FeatureGroup(
    name="Elevation Contours",
    show=True
)

folium.GeoJson(
    gdf,
    style_function=elevation_style,
    tooltip=folium.GeoJsonTooltip(
        fields=[elevation_col],
        aliases=["Elevation:"]
    )
).add_to(contour_layer)

contour_layer.add_to(mymap)

# ============================================================
# DOWNLOAD POPULATION DATA
# ============================================================

population_url = (
    "https://geo.stat.fi/geoserver/wfs"
    "?service=WFS"
    "&version=2.0.0"
    "&request=GetFeature"
    "&typeName=postialue:pno_tilasto"
    "&outputFormat=application/json"
)

pop_gdf = gpd.read_file(population_url)

pop_gdf = pop_gdf.to_crs(epsg=4326)

# ============================================================
# FILTER TO BBOX
# ============================================================

bbox_geom = box(
    MIN_LON,
    MIN_LAT,
    MAX_LON,
    MAX_LAT
)

pop_gdf = pop_gdf[
    pop_gdf.intersects(bbox_geom)
]

# ============================================================
# POPULATION DENSITY
# ============================================================

pop_gdf["density"] = (
    pop_gdf["he_vakiy"] /
    (pop_gdf["pinta_ala"] / 1000000.0)
)

pop_gdf["density"] = pop_gdf["density"].fillna(0)

# ============================================================
# POPULATION COLOR SCALE
# ============================================================

min_density = pop_gdf["density"].min()
max_density = pop_gdf["density"].max()

density_colormap = linear.YlOrRd_09.scale(
    min_density,
    max_density
)

# ============================================================
# POPULATION STYLE
# ============================================================

def population_style(feature):

    density = feature["properties"]["density"]

    return {
        "fillColor": density_colormap(density),
        "color": "black",
        "weight": 1,
        "fillOpacity": 0.6
    }

# ============================================================
# POPULATION LAYER
# ============================================================

population_layer = folium.FeatureGroup(
    name="Population Density",
    show=False
)

folium.GeoJson(
    pop_gdf,
    style_function=population_style,
    tooltip=folium.GeoJsonTooltip(
        fields=[
            "postinumeroalue",
            "nimi",
            "he_vakiy",
            "density"
        ],
        aliases=[
            "Zip Code:",
            "Area Name:",
            "Population:",
            "Density:"
        ]
    )
).add_to(population_layer)

population_layer.add_to(mymap)

# ============================================================
# DOWNLOAD ELECTRICITY DATA
# ============================================================

tags = {
    "power": True
}

power_gdf = ox.features.features_from_bbox(
    (MIN_LON, MIN_LAT, MAX_LON, MAX_LAT),
    tags
)

power_gdf = power_gdf[
    power_gdf.geometry.notna()
]

power_gdf = power_gdf.to_crs(epsg=4326)

# ============================================================
# ELECTRICITY SUBLAYERS
# ============================================================

line_layer = folium.FeatureGroup(name="Lines", show=False)
substation_layer = folium.FeatureGroup(name="Substations", show=False)
transformer_layer = folium.FeatureGroup(name="Transformers", show=False)
plant_layer = folium.FeatureGroup(name="Plants", show=False)
catenary_layer = folium.FeatureGroup(name="Catenary", show=False)
other_layer = folium.FeatureGroup(name="Other", show=False)

# ============================================================
# FILTER ELECTRICITY TYPES
# ============================================================

lines = power_gdf[
    power_gdf["power"].isin([
        "line",
        "minor_line",
        "cable"
    ])
]

substations = power_gdf[
    power_gdf["power"] == "substation"
]

transformers = power_gdf[
    power_gdf["power"] == "transformer"
]

plants = power_gdf[
    power_gdf["power"] == "plant"
]

catenary = power_gdf[
    power_gdf["power"] == "catenary_mast"
]

known_values = {
    "line",
    "minor_line",
    "cable",
    "substation",
    "transformer",
    "plant",
    "catenary_mast"
}

other = power_gdf[
    ~power_gdf["power"].isin(known_values)
]

# ============================================================
# STYLE HELPER
# ============================================================

def style_color(color):

    return lambda feature: {
        "color": color,
        "weight": 2,
        "fillColor": color,
        "fillOpacity": 0.5
    }

# ============================================================
# ADD LINE/POLYGON LAYERS
# ============================================================

folium.GeoJson(
    lines,
    style_function=style_color("red"),
    tooltip=folium.GeoJsonTooltip(fields=["power"])
).add_to(line_layer)

folium.GeoJson(
    substations,
    style_function=style_color("purple"),
    tooltip=folium.GeoJsonTooltip(fields=["power"])
).add_to(substation_layer)

folium.GeoJson(
    plants,
    style_function=style_color("black"),
    tooltip=folium.GeoJsonTooltip(fields=["power"])
).add_to(plant_layer)

folium.GeoJson(
    other,
    style_function=style_color("gray"),
    tooltip=folium.GeoJsonTooltip(fields=["power"])
).add_to(other_layer)

# ============================================================
# ADD POINT LAYERS
# ============================================================

for _, row in transformers.iterrows():

    geom = row.geometry

    if geom.geom_type == "Point":

        folium.CircleMarker(
            location=[geom.y, geom.x],
            radius=3,
            color="yellow",
            fill=True,
            fill_opacity=0.8,
            tooltip="transformer"
        ).add_to(transformer_layer)

for _, row in catenary.iterrows():

    geom = row.geometry

    if geom.geom_type == "Point":

        folium.CircleMarker(
            location=[geom.y, geom.x],
            radius=3,
            color="green",
            fill=True,
            fill_opacity=0.8,
            tooltip="catenary_mast"
        ).add_to(catenary_layer)

# ============================================================
# ADD ELECTRICITY LAYERS
# ============================================================

line_layer.add_to(mymap)
substation_layer.add_to(mymap)
transformer_layer.add_to(mymap)
plant_layer.add_to(mymap)
catenary_layer.add_to(mymap)
other_layer.add_to(mymap)

# ============================================================
# LOAD CELL TOWERS
# ============================================================

cols = [
    'radio','mcc','net','area','cell','unit',
    'lon','lat','range','samples','changeable',
    'created','updated','averageSignal'
]

cell_tower_data = pd.read_csv(
    '/content/244.csv.gz',
    compression='gzip',
    header=None,
    names=cols,
    index_col=False,
    sep=',',
    quotechar='"'
)

# ============================================================
# FILTER TOWERS
# ============================================================

filtered_towers = cell_tower_data[
    (cell_tower_data["lat"] >= MIN_LAT - 0.05) &
    (cell_tower_data["lat"] <= MAX_LAT + 0.05) &
    (cell_tower_data["lon"] >= MIN_LON - 0.1) &
    (cell_tower_data["lon"] <= MAX_LON + 0.1)
].dropna(subset=["lat", "lon"])

# ============================================================
# TOWER GROUP
# ============================================================

tower_group = folium.FeatureGroup(
    name="Cell Towers",
    show=False
)

# ============================================================
# ADD TOWERS
# ============================================================

for _, row in filtered_towers.iterrows():

    folium.CircleMarker(
        location=[row["lat"], row["lon"]],
        radius=2,
        color="blue",
        fill=True,
        fill_opacity=0.6,
        popup=folium.Popup(
            f"""
            <b>Radio:</b> {row['radio']}<br>
            <b>Net:</b> {row['net']}<br>
            <b>Range:</b> {row['range']} m<br>
            """,
            max_width=250
        )
    ).add_to(tower_group)

# ============================================================
# COVERAGE
# ============================================================

if len(filtered_towers) > 0:

    tower_gdf = gpd.GeoDataFrame(
        filtered_towers,
        geometry=gpd.points_from_xy(
            filtered_towers.lon,
            filtered_towers.lat
        ),
        crs="EPSG:4326"
    ).to_crs(epsg=3857)

    tower_gdf["range"] = (
        tower_gdf["range"]
        .fillna(0)
        .clip(0, 5000)
    )

    tower_gdf["geometry"] = (
        tower_gdf.geometry.buffer(
            tower_gdf["range"]
        )
    )

    coverage = tower_gdf.geometry.union_all()

    coverage_gdf = gpd.GeoDataFrame(
        geometry=[coverage],
        crs="EPSG:3857"
    ).to_crs(epsg=4326)

    folium.GeoJson(
        coverage_gdf,
        style_function=lambda x: {
            "fillColor": "blue",
            "color": "blue",
            "weight": 1,
            "fillOpacity": 0.25,
            "interactive": False
        }
    ).add_to(tower_group)

tower_group.add_to(mymap)

# ============================================================
# FETCH WEATHER DATA (FMI Open Data)
# ============================================================

FMI_URL = "https://opendata.fmi.fi/wfs/eng"

now = datetime.now(timezone.utc)
weather_start = now
weather_end   = now + timedelta(days=2)

# Model selection: harmonie ≤3 days, ecmwf ≤9 days
delta_days = (weather_end - now).total_seconds() / (3600 * 24)

if delta_days <= 3:
    sqid = "harmonie::forecast::surface::point::simple"
elif delta_days <= 9:
    sqid = "ecmwf::forecast::surface::point::simple"
else:
    raise Exception("Forecast range exceeds 9 days.")

weather_params = {
    "service": "WFS",
    "version": "2.0.0",
    "request": "getFeature",
    "storedquery_id": sqid,
    "latlon": f"{center_lat},{center_lon}",
    "parameters": "temperature,humidity,windspeedms,weathersymbol3",
    "starttime": weather_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "endtime": weather_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
}

weather_xml = requests.get(
    FMI_URL,
    params=weather_params,
    timeout=60
).text

# ============================================================
# PARSE WEATHER XML
# ============================================================

root_wx = ET.fromstring(weather_xml)

ns = {
    "wfs":   "http://www.opengis.net/wfs/2.0",
    "BsWfs": "http://xml.fmi.fi/schema/wfs/2.0",
}

# Collect records: {time -> {param -> value}}
weather_records = {}

for member in root_wx.findall("wfs:member", ns):

    time_el  = member.find(".//BsWfs:Time", ns)
    param_el = member.find(".//BsWfs:ParameterName", ns)
    value_el = member.find(".//BsWfs:ParameterValue", ns)

    if time_el is None:
        continue

    t = time_el.text.strip()
    p = param_el.text.strip()
    v = value_el.text.strip()

    if t not in weather_records:
        weather_records[t] = {}

    try:
        weather_records[t][p] = float(v)
    except ValueError:
        weather_records[t][p] = v

# Sort by time
weather_records = dict(sorted(weather_records.items()))

# ============================================================
# WEATHER SYMBOL MAPPING
# ============================================================

WEATHER_ICONS = {
    1:  ("☀️",  "Clear"),
    2:  ("🌤️",  "Mostly clear"),
    3:  ("⛅",  "Partly cloudy"),
    4:  ("🌥️",  "Mostly cloudy"),
    21: ("🌦️",  "Light rain"),
    22: ("🌧️",  "Moderate rain"),
    23: ("🌧️",  "Heavy rain"),
    31: ("🌨️",  "Light sleet"),
    32: ("🌨️",  "Moderate sleet"),
    33: ("🌨️",  "Heavy sleet"),
    41: ("🌨️",  "Light snow"),
    42: ("❄️",  "Moderate snow"),
    43: ("❄️",  "Heavy snow"),
    51: ("⛈️",  "Light thunderstorm"),
    52: ("⛈️",  "Moderate thunderstorm"),
    53: ("⛈️",  "Heavy thunderstorm"),
    61: ("🌩️",  "Light hail"),
    62: ("🌩️",  "Heavy hail"),
}

def wx_icon(symbol_val):
    try:
        s = int(symbol_val)
        return WEATHER_ICONS.get(s, ("🌡️", f"Symbol {s}"))
    except (TypeError, ValueError):
        return ("🌡️", "Unknown")

# ============================================================
# BUILD WEATHER LAYER
# ============================================================

weather_layer = folium.FeatureGroup(
    name="Weather Forecast",
    show=False
)

# Group records into hourly steps and place a marker for each
for time_str, vals in weather_records.items():

    temp     = vals.get("temperature",    None)
    humidity = vals.get("humidity",       None)
    wind     = vals.get("windspeedms",    None)
    symbol   = vals.get("weathersymbol3", None)

    # Only add marker when we have at least temperature
    if temp is None:
        continue

    icon_char, icon_label = wx_icon(symbol)

    # Format readable time
    try:
        dt_obj   = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        time_fmt = dt_obj.strftime("%d %b %H:%M UTC")
    except Exception:
        time_fmt = time_str

    popup_html = f"""
    <div style="font-family:sans-serif; min-width:160px;">
        <b style="font-size:14px;">{icon_char} {time_fmt}</b><br>
        <hr style="margin:4px 0;">
        <b>Condition:</b> {icon_label}<br>
        <b>Temperature:</b> {temp:.1f} °C<br>
        {"<b>Humidity:</b> " + f"{humidity:.0f} %" + "<br>" if humidity is not None else ""}
        {"<b>Wind:</b> " + f"{wind:.1f} m/s" + "<br>" if wind is not None else ""}
    </div>
    """

    # Offset each marker slightly so they don't stack exactly
    # (FMI returns the same lat/lon for all; small jitter makes timeline browsable)
    dt_index = list(weather_records.keys()).index(time_str)
    jitter_lon = center_lon + (dt_index % 20) * 0.0004 - 0.004
    jitter_lat = center_lat - (dt_index // 20) * 0.0006

    folium.Marker(
        location=[jitter_lat, jitter_lon],
        popup=folium.Popup(popup_html, max_width=220),
        tooltip=f"{icon_char} {time_fmt} | {temp:.1f}°C",
        icon=folium.DivIcon(
            html=f"""
            <div style="
                background: rgba(255,255,255,0.85);
                border: 1px solid #999;
                border-radius: 6px;
                padding: 2px 5px;
                font-size: 11px;
                font-family: sans-serif;
                white-space: nowrap;
                box-shadow: 1px 1px 3px rgba(0,0,0,0.3);
            ">
                {icon_char} {temp:.1f}°C
            </div>
            """,
            icon_size=(70, 24),
            icon_anchor=(35, 12)
        )
    ).add_to(weather_layer)

weather_layer.add_to(mymap)

# ============================================================
# LEGENDS
# ============================================================

elev_colormap.caption = "Elevation"
density_colormap.caption = "Population Density"

mymap.add_child(elev_colormap)
mymap.add_child(density_colormap)

# ============================================================
# MOVE LEGENDS LEFT
# ============================================================

legend_css = """
<style>

.leaflet-control {
    clear: both;
}

.leaflet-bottom.leaflet-right {
    right: auto !important;
    left: 10px !important;
}

</style>
"""

mymap.get_root().header.add_child(
    folium.Element(legend_css)
)

# ============================================================
# TREE LAYER CONTROL
# ============================================================

TreeLayerControl(
    overlay_tree={
        "label": "Layers",
        "children": [
            {
                "label": "Elevation",
                "layer": contour_layer
            },
            {
                "label": "Population",
                "layer": population_layer
            },
            {
                "label": "Cell Towers",
                "layer": tower_group
            },
            {
                "label": "Weather Forecast",
                "layer": weather_layer
            },
            {
                "label": "Electricity",
                "select_all_checkbox": True,
                "children": [
                    {
                        "label": "Lines",
                        "layer": line_layer
                    },
                    {
                        "label": "Substations",
                        "layer": substation_layer
                    },
                    {
                        "label": "Transformers",
                        "layer": transformer_layer
                    },
                    {
                        "label": "Plants",
                        "layer": plant_layer
                    },
                    {
                        "label": "Catenary",
                        "layer": catenary_layer
                    },
                    {
                        "label": "Other",
                        "layer": other_layer
                    }
                ]
            }
        ]
    },
    collapsed=False
).add_to(mymap)

# ============================================================
# SHOW MAP
# ============================================================

mymap
