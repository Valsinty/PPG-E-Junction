# ============================================================
# app.py — Geo Infrastructure Dashboard
# Streamlit Community Cloud deployment
# ============================================================

import streamlit as st
from streamlit_folium import st_folium

import requests
import geopandas as gpd
import folium
import osmnx as ox
import pandas as pd

from branca.colormap import linear
from shapely.geometry import box
from folium.plugins import TreeLayerControl, Draw

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="Geo Infrastructure Dashboard",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ Geo Infrastructure Dashboard")

# ============================================================
# SESSION STATE
# ============================================================
if "bbox" not in st.session_state:
    st.session_state.bbox = None  # (MIN_LON, MIN_LAT, MAX_LON, MAX_LAT)

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.header("📍 Alan Seçimi")
    st.markdown("**Yöntem 1:** Harita üzerinde dikdörtgen çiz")
    st.markdown("**Yöntem 2:** Koordinat gir")

    st.divider()
    st.subheader("Manuel Koordinat Girişi")

    col1, col2 = st.columns(2)
    with col1:
        MIN_LON_input = st.number_input("Min Lon", value=24.80, format="%.4f", step=0.01)
        MIN_LAT_input = st.number_input("Min Lat", value=60.10, format="%.4f", step=0.01)
    with col2:
        MAX_LON_input = st.number_input("Max Lon", value=25.10, format="%.4f", step=0.01)
        MAX_LAT_input = st.number_input("Max Lat", value=60.30, format="%.4f", step=0.01)

    if st.button("📌 Bu Koordinatları Kullan", use_container_width=True):
        st.session_state.bbox = (MIN_LON_input, MIN_LAT_input, MAX_LON_input, MAX_LAT_input)
        st.rerun()

    st.divider()

    if st.session_state.bbox:
        b = st.session_state.bbox
        st.markdown("**Seçili Alan:**")
        st.code(f"Min Lon: {b[0]:.4f}\nMin Lat: {b[1]:.4f}\nMax Lon: {b[2]:.4f}\nMax Lat: {b[3]:.4f}")
        run = st.button("🚀 Analizi Başlat", use_container_width=True, type="primary")
    else:
        st.info("Henüz alan seçilmedi.")
        run = False

# ============================================================
# STEP 1 — DRAW MAP
# ============================================================
if not run:
    st.markdown("### 1️⃣ Analiz alanını seç")
    st.markdown("Haritada sol üstteki **dikdörtgen aracını** kullanarak alan çiz, veya soldaki panelden koordinat gir.")

    draw_map = folium.Map(location=[60.2, 24.9], zoom_start=8, tiles="OpenStreetMap")

    if st.session_state.bbox:
        b = st.session_state.bbox
        folium.Rectangle(
            bounds=[[b[1], b[0]], [b[3], b[2]]],
            color="blue", fill=True, fill_opacity=0.1, tooltip="Seçili alan"
        ).add_to(draw_map)

    Draw(
        draw_options={
            "rectangle": True,
            "polygon": False,
            "polyline": False,
            "circle": False,
            "marker": False,
            "circlemarker": False,
        },
        edit_options={"edit": False}
    ).add_to(draw_map)

    draw_result = st_folium(draw_map, width=None, height=500, returned_objects=["all_drawings"])

    if draw_result and draw_result.get("all_drawings"):
        drawings = draw_result["all_drawings"]
        if drawings:
            last = drawings[-1]
            if last.get("geometry", {}).get("type") == "Polygon":
                coords = last["geometry"]["coordinates"][0]
                lons = [c[0] for c in coords]
                lats = [c[1] for c in coords]
                drawn_bbox = (min(lons), min(lats), max(lons), max(lats))
                if drawn_bbox != st.session_state.bbox:
                    st.session_state.bbox = drawn_bbox
                    st.rerun()

# ============================================================
# STEP 2 — ANALYSIS
# ============================================================
if run and st.session_state.bbox:

    MIN_LON, MIN_LAT, MAX_LON, MAX_LAT = st.session_state.bbox
    BBOX = f"{MIN_LON},{MIN_LAT},{MAX_LON},{MAX_LAT}"

    try:
        API_KEY = st.secrets["API_KEY"]
    except Exception:
        API_KEY = "1d9d451c-28be-4deb-b051-9bd521a062db"

    st.markdown("### 2️⃣ Analiz Sonuçları")

    center_lat = (MIN_LAT + MAX_LAT) / 2
    center_lon = (MIN_LON + MAX_LON) / 2

    mymap = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="OpenStreetMap")

    folium.Rectangle(
        bounds=[[MIN_LAT, MIN_LON], [MAX_LAT, MAX_LON]],
        color="blue", fill=False, weight=2, dash_array="6", tooltip="Analiz alanı"
    ).add_to(mymap)

    # ----------------------------------------------------------
    # ELEVATION CONTOURS
    # ----------------------------------------------------------
    with st.status("🏔️ Yükseklik konturları yükleniyor..."):
        try:
            url = (
                "https://avoin-paikkatieto.maanmittauslaitos.fi/"
                "maastotiedot/features/v1/collections/korkeuskayra/items"
            )
            response = requests.get(
                url,
                params={"bbox": BBOX, "limit": 10000, "f": "json", "api-key": API_KEY},
                timeout=60
            )
            response.raise_for_status()
            data = response.json()
            gdf = gpd.GeoDataFrame.from_features(data["features"])
            elevation_col = "korkeusarvo"

            if not gdf.empty and elevation_col in gdf.columns:
                gdf = gdf[gdf[elevation_col].notna()].set_crs(epsg=4326, allow_override=True)
                elev_colormap = linear.YlOrRd_09.scale(gdf[elevation_col].min(), gdf[elevation_col].max())

                def elevation_style(feature):
                    return {"color": elev_colormap(feature["properties"][elevation_col]), "weight": 2, "opacity": 0.8}

                contour_layer = folium.FeatureGroup(name="Elevation Contours", show=True)
                folium.GeoJson(gdf, style_function=elevation_style,
                               tooltip=folium.GeoJsonTooltip(fields=[elevation_col], aliases=["Elevation:"])
                               ).add_to(contour_layer)
                st.write("✅ Yükseklik konturları yüklendi.")
            else:
                contour_layer = folium.FeatureGroup(name="Elevation Contours (No Data)", show=True)
                elev_colormap = None
                st.write("⚠️ Yükseklik verisi bulunamadı.")
        except Exception as e:
            contour_layer = folium.FeatureGroup(name="Elevation Contours (Error)", show=True)
            elev_colormap = None
            st.write(f"⚠️ Yükseklik verisi yüklenemedi: {e}")

    contour_layer.add_to(mymap)

    # ----------------------------------------------------------
    # POPULATION DENSITY
    # ----------------------------------------------------------
    with st.status("👥 Nüfus yoğunluğu yükleniyor..."):
        try:
            population_url = (
                "https://geo.stat.fi/geoserver/wfs"
                "?service=WFS&version=2.0.0&request=GetFeature"
                "&typeName=postialue:pno_tilasto&outputFormat=application/json"
            )
            pop_gdf = gpd.read_file(population_url).to_crs(epsg=4326)
            pop_gdf = pop_gdf[pop_gdf.intersects(box(MIN_LON, MIN_LAT, MAX_LON, MAX_LAT))]
            population_layer = folium.FeatureGroup(name="Population Density", show=False)

            if not pop_gdf.empty:
                pop_gdf["density"] = (pop_gdf["he_vakiy"] / (pop_gdf["pinta_ala"] / 1000000.0)).fillna(0)
                density_colormap = linear.YlGnBu_09.scale(pop_gdf["density"].min(), pop_gdf["density"].max())

                def population_style(feature):
                    return {"fillColor": density_colormap(feature["properties"]["density"]),
                            "color": "black", "weight": 1, "fillOpacity": 0.6}

                folium.GeoJson(pop_gdf, style_function=population_style,
                               tooltip=folium.GeoJsonTooltip(
                                   fields=["postinumeroalue", "nimi", "he_vakiy", "density"],
                                   aliases=["Zip Code:", "Area Name:", "Population:", "Density:"]
                               )).add_to(population_layer)
                st.write("✅ Nüfus yoğunluğu yüklendi.")
            else:
                density_colormap = None
                st.write("⚠️ Nüfus verisi bulunamadı.")
        except Exception as e:
            population_layer = folium.FeatureGroup(name="Population Density (Error)", show=False)
            density_colormap = None
            st.write(f"⚠️ Nüfus verisi yüklenemedi: {e}")

    population_layer.add_to(mymap)

    # ----------------------------------------------------------
    # ELECTRICITY
    # ----------------------------------------------------------
    with st.status("⚡ Elektrik altyapısı yükleniyor..."):
        line_layer        = folium.FeatureGroup(name="Lines",        show=False)
        substation_layer  = folium.FeatureGroup(name="Substations",  show=False)
        transformer_layer = folium.FeatureGroup(name="Transformers", show=False)
        plant_layer       = folium.FeatureGroup(name="Plants",       show=False)
        catenary_layer    = folium.FeatureGroup(name="Catenary",     show=False)
        other_layer       = folium.FeatureGroup(name="Other",        show=False)
        try:
            power_gdf = ox.features.features_from_bbox((MIN_LON, MIN_LAT, MAX_LON, MAX_LAT), {"power": True})

            def style_color(color):
                return lambda feature: {"color": color, "weight": 2, "fillColor": color, "fillOpacity": 0.5}

            if not power_gdf.empty:
                power_gdf = power_gdf[power_gdf.geometry.notna()].to_crs(epsg=4326)
                if "power" in power_gdf.columns:
                    lines = power_gdf[power_gdf["power"].isin(["line", "minor_line", "cable"])]
                    if not lines.empty:
                        folium.GeoJson(lines, style_function=style_color("red"),
                                       tooltip=folium.GeoJsonTooltip(fields=["power"])).add_to(line_layer)
                    substations = power_gdf[power_gdf["power"] == "substation"]
                    if not substations.empty:
                        folium.GeoJson(substations, style_function=style_color("purple"),
                                       tooltip=folium.GeoJsonTooltip(fields=["power"])).add_to(substation_layer)
                    plants = power_gdf[power_gdf["power"] == "plant"]
                    if not plants.empty:
                        folium.GeoJson(plants, style_function=style_color("black"),
                                       tooltip=folium.GeoJsonTooltip(fields=["power"])).add_to(plant_layer)
                    for _, row in power_gdf[power_gdf["power"] == "transformer"].iterrows():
                        if row.geometry.geom_type == "Point":
                            folium.CircleMarker(location=[row.geometry.y, row.geometry.x], radius=3,
                                                color="yellow", fill=True, fill_opacity=0.8,
                                                tooltip="transformer").add_to(transformer_layer)
                    for _, row in power_gdf[power_gdf["power"] == "catenary_mast"].iterrows():
                        if row.geometry.geom_type == "Point":
                            folium.CircleMarker(location=[row.geometry.y, row.geometry.x], radius=3,
                                                color="green", fill=True, fill_opacity=0.8,
                                                tooltip="catenary_mast").add_to(catenary_layer)
                    known = {"line", "minor_line", "cable", "substation", "transformer", "plant", "catenary_mast"}
                    other = power_gdf[~power_gdf["power"].isin(known)]
                    if not other.empty:
                        folium.GeoJson(other, style_function=style_color("gray"),
                                       tooltip=folium.GeoJsonTooltip(fields=["power"])).add_to(other_layer)
            st.write("✅ Elektrik altyapısı yüklendi.")
        except Exception as e:
            st.write(f"⚠️ Elektrik verisi yüklenemedi: {e}")

    line_layer.add_to(mymap)
    substation_layer.add_to(mymap)
    transformer_layer.add_to(mymap)
    plant_layer.add_to(mymap)
    catenary_layer.add_to(mymap)
    other_layer.add_to(mymap)

    # ----------------------------------------------------------
    # CELL TOWERS
    # ----------------------------------------------------------
    with st.status("📡 Baz istasyonları yükleniyor..."):
        cols = ['radio','mcc','net','area','cell','unit','lon','lat','range','samples','changeable','created','updated','averageSignal']
        tower_group = folium.FeatureGroup(name="Cell Towers", show=False)
        try:
            cell_tower_data = pd.read_csv('244.csv.gz', compression='gzip', header=None,
                                          names=cols, index_col=False, sep=',', quotechar='"')
            filtered_towers = cell_tower_data[
                (cell_tower_data["lat"] >= MIN_LAT - 0.05) & (cell_tower_data["lat"] <= MAX_LAT + 0.05) &
                (cell_tower_data["lon"] >= MIN_LON - 0.1)  & (cell_tower_data["lon"] <= MAX_LON + 0.1)
            ].dropna(subset=["lat", "lon"])
            st.write(f"✅ {len(filtered_towers)} baz istasyonu bulundu.")

            for _, row in filtered_towers.iterrows():
                folium.CircleMarker(
                    location=[row["lat"], row["lon"]], radius=2, color="blue",
                    fill=True, fill_opacity=0.6,
                    popup=folium.Popup(f"<b>Radio:</b> {row['radio']}<br><b>Net:</b> {row['net']}<br><b>Range:</b> {row['range']} m", max_width=250)
                ).add_to(tower_group)

            tower_gdf = gpd.GeoDataFrame(filtered_towers,
                                         geometry=gpd.points_from_xy(filtered_towers.lon, filtered_towers.lat),
                                         crs="EPSG:4326").to_crs(epsg=3857)
            tower_gdf["range"] = tower_gdf["range"].fillna(0).clip(0, 5000)
            tower_gdf["geometry"] = tower_gdf.geometry.buffer(tower_gdf["range"])
            coverage = tower_gdf.geometry.union_all()
            coverage_gdf = gpd.GeoDataFrame(geometry=[coverage], crs="EPSG:3857").to_crs(epsg=4326)
            folium.GeoJson(coverage_gdf,
                           style_function=lambda x: {"fillColor": "blue", "color": "blue",
                                                     "weight": 1, "fillOpacity": 0.25, "interactive": False}
                           ).add_to(tower_group)
        except FileNotFoundError:
            st.write("⚠️ 244.csv.gz bulunamadı.")

    tower_group.add_to(mymap)

    # ----------------------------------------------------------
    # PUBLIC SERVICES
    # ----------------------------------------------------------
    with st.status("🏥 Kamu hizmetleri yükleniyor..."):
        hospital_layer   = folium.FeatureGroup(name="Hospitals",     show=False)
        school_layer     = folium.FeatureGroup(name="Schools",       show=False)
        university_layer = folium.FeatureGroup(name="Universities",  show=False)
        police_layer     = folium.FeatureGroup(name="Police",        show=False)
        fire_layer       = folium.FeatureGroup(name="Fire Stations", show=False)
        try:
            public_gdf = ox.features.features_from_bbox(
                (MIN_LON, MIN_LAT, MAX_LON, MAX_LAT),
                {"amenity": ["hospital", "school", "university", "police", "fire_station"]}
            )
            if not public_gdf.empty:
                public_gdf = public_gdf[public_gdf.geometry.notna()].to_crs(epsg=4326)

                def add_point_markers(gdf_subset, layer, color, label):
                    for _, row in gdf_subset.iterrows():
                        geom = row.geometry
                        name = row.get("name", "Unnamed")
                        pt = geom if geom.geom_type == "Point" else (geom.centroid if geom.geom_type in ["Polygon", "MultiPolygon"] else None)
                        if pt:
                            folium.CircleMarker(location=[pt.y, pt.x], radius=5, color=color,
                                                fill=True, fill_opacity=0.8, popup=f"{label}: {name}").add_to(layer)

                add_point_markers(public_gdf[public_gdf["amenity"] == "hospital"],     hospital_layer,   "red",    "Hospital")
                add_point_markers(public_gdf[public_gdf["amenity"] == "school"],       school_layer,     "blue",   "School")
                add_point_markers(public_gdf[public_gdf["amenity"] == "university"],   university_layer, "purple", "University")
                add_point_markers(public_gdf[public_gdf["amenity"] == "police"],       police_layer,     "black",  "Police")
                add_point_markers(public_gdf[public_gdf["amenity"] == "fire_station"], fire_layer,       "orange", "Fire Station")
            st.write("✅ Kamu hizmetleri yüklendi.")
        except Exception as e:
            st.write(f"⚠️ Kamu hizmetleri yüklenemedi: {e}")

    hospital_layer.add_to(mymap)
    school_layer.add_to(mymap)
    university_layer.add_to(mymap)
    police_layer.add_to(mymap)
    fire_layer.add_to(mymap)

    # ----------------------------------------------------------
    # RAILWAY NETWORK
    # ----------------------------------------------------------
    with st.status("🚆 Demiryolu ağı yükleniyor..."):
        from bs4 import BeautifulSoup

        rail_layer    = folium.FeatureGroup(name="Railways",         show=False)
        station_layer = folium.FeatureGroup(name="Railway Stations", show=False)
        node_layer    = folium.FeatureGroup(name="Railway Nodes",    show=False)

        rail_base_url = (
            "https://avoinapi.vaylapilvi.fi/inspirepalvelu/tn-ra/wfs"
            "?service=WFS&version=2.0.0&request=GetFeature"
        )
        bbox_3067 = gpd.GeoSeries([box(MIN_LON, MIN_LAT, MAX_LON, MAX_LAT)], crs="EPSG:4326").to_crs(epsg=3067)
        minx, miny, maxx, maxy = bbox_3067.total_bounds
        rail_bbox = f"{minx},{miny},{maxx},{maxy}"

        try:
            railway_gdf = gpd.read_file(f"{rail_base_url}&typeNames=tn-ra:RailwayLink&bbox={rail_bbox},EPSG:3067")
            if not railway_gdf.empty:
                folium.GeoJson(railway_gdf.to_crs(epsg=4326),
                               style_function=lambda f: {"color": "black", "weight": 3, "opacity": 0.9},
                               tooltip=folium.GeoJsonTooltip(fields=["gml_id"], aliases=["Rail ID:"])
                               ).add_to(rail_layer)
        except Exception as e:
            st.write(f"⚠️ Demiryolu hattı yüklenemedi: {e}")

        for url_type, layer, radius, color, label in [
            ("RailwayStationNode", station_layer, 5, "red",    "Railway Station"),
            ("RailwayNode",        node_layer,    3, "orange", "Railway Node"),
        ]:
            try:
                r = requests.get(f"{rail_base_url}&typeNames=tn-ra:{url_type}&bbox={rail_bbox},EPSG:3067", timeout=60)
                r.raise_for_status()
                for pos in BeautifulSoup(r.text, "xml").find_all("gml:pos"):
                    coords = pos.text.strip().split()
                    if len(coords) >= 2:
                        pt = gpd.GeoSeries.from_xy([float(coords[0])], [float(coords[1])], crs="EPSG:3067").to_crs(epsg=4326)
                        folium.CircleMarker(location=[pt.y.iloc[0], pt.x.iloc[0]], radius=radius,
                                            color=color, fill=True, fill_opacity=0.9, popup=label).add_to(layer)
            except Exception as e:
                st.write(f"⚠️ {url_type} yüklenemedi: {e}")

        st.write("✅ Demiryolu ağı tamamlandı.")

    rail_layer.add_to(mymap)
    station_layer.add_to(mymap)
    node_layer.add_to(mymap)

    # ----------------------------------------------------------
    # LEGENDS & LAYER CONTROL
    # ----------------------------------------------------------
    if elev_colormap:
        elev_colormap.caption = "Elevation"
        mymap.add_child(elev_colormap)
    if density_colormap:
        density_colormap.caption = "Population Density"
        mymap.add_child(density_colormap)

    mymap.get_root().header.add_child(folium.Element("""
    <style>
    .leaflet-control { clear: both; }
    .leaflet-bottom.leaflet-right { right: auto !important; left: 10px !important; }
    </style>
    """))

    TreeLayerControl(
        overlay_tree={
            "label": "Layers",
            "children": [
                {"label": "Elevation",   "layer": contour_layer},
                {"label": "Population",  "layer": population_layer},
                {"label": "Cell Towers", "layer": tower_group},
                {"label": "Electricity", "select_all_checkbox": True, "children": [
                    {"label": "Lines",        "layer": line_layer},
                    {"label": "Substations",  "layer": substation_layer},
                    {"label": "Transformers", "layer": transformer_layer},
                    {"label": "Plants",       "layer": plant_layer},
                    {"label": "Catenary",     "layer": catenary_layer},
                    {"label": "Other",        "layer": other_layer},
                ]},
                {"label": "Public Services", "select_all_checkbox": True, "children": [
                    {"label": "Hospitals",    "layer": hospital_layer},
                    {"label": "Schools",      "layer": school_layer},
                    {"label": "Universities", "layer": university_layer},
                    {"label": "Police",       "layer": police_layer},
                    {"label": "Fire Stations","layer": fire_layer},
                ]},
                {"label": "Railways", "select_all_checkbox": True, "children": [
                    {"label": "Tracks",   "layer": rail_layer},
                    {"label": "Stations", "layer": station_layer},
                    {"label": "Nodes",    "layer": node_layer},
                ]},
            ]
        },
        collapsed=False
    ).add_to(mymap)

    st.success("✅ Analiz tamamlandı!")
    st_folium(mymap, width=None, height=750, returned_objects=[])

    if st.button("🔄 Yeni Alan Seç"):
        st.session_state.bbox = None
        st.rerun()
