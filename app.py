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
from folium.plugins import TreeLayerControl

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="Geo Infrastructure Dashboard",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ Geo Infrastructure Dashboard")
st.markdown("Harita üzerinde analiz yapmak istediğin bölgenin koordinatlarını gir ve analizi başlat.")

# ============================================================
# SIDEBAR — BBOX INPUT
# ============================================================
with st.sidebar:
    st.header("📍 Bounding Box")
    st.markdown("Analiz edilecek alanın koordinatları:")

    MIN_LON = st.number_input("Min Longitude", value=24.80, format="%.4f", step=0.01)
    MIN_LAT = st.number_input("Min Latitude",  value=60.10, format="%.4f", step=0.01)
    MAX_LON = st.number_input("Max Longitude", value=25.10, format="%.4f", step=0.01)
    MAX_LAT = st.number_input("Max Latitude",  value=60.30, format="%.4f", step=0.01)

    st.divider()

    st.markdown("**Katmanlar** haritada TreeLayerControl ile açılıp kapatılabilir.")

    run = st.button("🚀 Analizi Başlat", use_container_width=True, type="primary")

# ============================================================
# MAIN LOGIC — only runs when user clicks the button
# ============================================================
if run:

    BBOX = f"{MIN_LON},{MIN_LAT},{MAX_LON},{MAX_LAT}"

    # API key — Streamlit secrets'tan okunur
    # share.streamlit.io → App Settings → Secrets bölümüne ekle:
    #   API_KEY = "1d9d451c-28be-4deb-b051-9bd521a062db"
    try:
        API_KEY = st.secrets["API_KEY"]
    except Exception:
        # Geliştirme ortamı için fallback
        API_KEY = "1d9d451c-28be-4deb-b051-9bd521a062db"

    # ----------------------------------------------------------
    # CREATE BASE MAP
    # ----------------------------------------------------------
    center_lat = (MIN_LAT + MAX_LAT) / 2
    center_lon = (MIN_LON + MAX_LON) / 2

    mymap = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=12,
        tiles="OpenStreetMap"
    )

    # ----------------------------------------------------------
    # ELEVATION CONTOURS
    # ----------------------------------------------------------
    with st.status("🏔️ Yükseklik konturları yükleniyor..."):
        try:
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

            gdf = gpd.GeoDataFrame.from_features(data["features"])
            elevation_col = "korkeusarvo"

            if not gdf.empty and elevation_col in gdf.columns:
                gdf = gdf[gdf[elevation_col].notna()]
                gdf = gdf.set_crs(epsg=4326, allow_override=True)

                min_elev = gdf[elevation_col].min()
                max_elev = gdf[elevation_col].max()
                elev_colormap = linear.YlOrRd_09.scale(min_elev, max_elev)

                def elevation_style(feature):
                    elev = feature["properties"][elevation_col]
                    return {"color": elev_colormap(elev), "weight": 2, "opacity": 0.8}

                contour_layer = folium.FeatureGroup(name="Elevation Contours", show=True)
                folium.GeoJson(
                    gdf,
                    style_function=elevation_style,
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
                "?service=WFS"
                "&version=2.0.0"
                "&request=GetFeature"
                "&typeName=postialue:pno_tilasto"
                "&outputFormat=application/json"
            )

            pop_gdf = gpd.read_file(population_url)
            pop_gdf = pop_gdf.to_crs(epsg=4326)

            bbox_geom = box(MIN_LON, MIN_LAT, MAX_LON, MAX_LAT)
            pop_gdf = pop_gdf[pop_gdf.intersects(bbox_geom)]

            population_layer = folium.FeatureGroup(name="Population Density", show=False)

            if not pop_gdf.empty:
                pop_gdf["density"] = pop_gdf["he_vakiy"] / (pop_gdf["pinta_ala"] / 1000000.0)
                pop_gdf["density"] = pop_gdf["density"].fillna(0)

                min_density = pop_gdf["density"].min()
                max_density = pop_gdf["density"].max()
                density_colormap = linear.YlGnBu_09.scale(min_density, max_density)

                def population_style(feature):
                    density = feature["properties"]["density"]
                    return {
                        "fillColor": density_colormap(density),
                        "color": "black",
                        "weight": 1,
                        "fillOpacity": 0.6
                    }

                folium.GeoJson(
                    pop_gdf,
                    style_function=population_style,
                    tooltip=folium.GeoJsonTooltip(
                        fields=["postinumeroalue", "nimi", "he_vakiy", "density"],
                        aliases=["Zip Code:", "Area Name:", "Population:", "Density:"]
                    )
                ).add_to(population_layer)
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
    # ELECTRICITY INFRASTRUCTURE
    # ----------------------------------------------------------
    with st.status("⚡ Elektrik altyapısı yükleniyor..."):
        try:
            tags = {"power": True}
            power_gdf = ox.features.features_from_bbox((MIN_LON, MIN_LAT, MAX_LON, MAX_LAT), tags)

            line_layer        = folium.FeatureGroup(name="Lines",        show=False)
            substation_layer  = folium.FeatureGroup(name="Substations",  show=False)
            transformer_layer = folium.FeatureGroup(name="Transformers", show=False)
            plant_layer       = folium.FeatureGroup(name="Plants",       show=False)
            catenary_layer    = folium.FeatureGroup(name="Catenary",     show=False)
            other_layer       = folium.FeatureGroup(name="Other",        show=False)

            def style_color(color):
                return lambda feature: {
                    "color": color,
                    "weight": 2,
                    "fillColor": color,
                    "fillOpacity": 0.5
                }

            if not power_gdf.empty:
                power_gdf = power_gdf[power_gdf.geometry.notna()]
                power_gdf = power_gdf.to_crs(epsg=4326)

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

                    transformers = power_gdf[power_gdf["power"] == "transformer"]
                    if not transformers.empty:
                        for _, row in transformers.iterrows():
                            geom = row.geometry
                            if geom.geom_type == "Point":
                                folium.CircleMarker(
                                    location=[geom.y, geom.x], radius=3, color="yellow",
                                    fill=True, fill_opacity=0.8, tooltip="transformer"
                                ).add_to(transformer_layer)

                    catenary = power_gdf[power_gdf["power"] == "catenary_mast"]
                    if not catenary.empty:
                        for _, row in catenary.iterrows():
                            geom = row.geometry
                            if geom.geom_type == "Point":
                                folium.CircleMarker(
                                    location=[geom.y, geom.x], radius=3, color="green",
                                    fill=True, fill_opacity=0.8, tooltip="catenary_mast"
                                ).add_to(catenary_layer)

                    known_values = {"line", "minor_line", "cable", "substation", "transformer", "plant", "catenary_mast"}
                    other = power_gdf[~power_gdf["power"].isin(known_values)]
                    if not other.empty:
                        folium.GeoJson(other, style_function=style_color("gray"),
                                       tooltip=folium.GeoJsonTooltip(fields=["power"])).add_to(other_layer)

            st.write("✅ Elektrik altyapısı yüklendi.")

        except Exception as e:
            line_layer        = folium.FeatureGroup(name="Lines",        show=False)
            substation_layer  = folium.FeatureGroup(name="Substations",  show=False)
            transformer_layer = folium.FeatureGroup(name="Transformers", show=False)
            plant_layer       = folium.FeatureGroup(name="Plants",       show=False)
            catenary_layer    = folium.FeatureGroup(name="Catenary",     show=False)
            other_layer       = folium.FeatureGroup(name="Other",        show=False)
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

        try:
            cell_tower_data = pd.read_csv(
                '244.csv.gz',
                compression='gzip',
                header=None,
                names=cols,
                index_col=False,
                sep=',',
                quotechar='"'
            )
            filtered_towers = cell_tower_data[
                (cell_tower_data["lat"] >= MIN_LAT - 0.05) & (cell_tower_data["lat"] <= MAX_LAT + 0.05) &
                (cell_tower_data["lon"] >= MIN_LON - 0.1)  & (cell_tower_data["lon"] <= MAX_LON + 0.1)
            ].dropna(subset=["lat", "lon"])
            st.write(f"✅ {len(filtered_towers)} baz istasyonu bulundu.")
        except FileNotFoundError:
            st.write("⚠️ 244.csv.gz bulunamadı. Baz istasyonları atlanıyor.")
            filtered_towers = pd.DataFrame()

        tower_group = folium.FeatureGroup(name="Cell Towers", show=False)

        if not filtered_towers.empty:
            for _, row in filtered_towers.iterrows():
                folium.CircleMarker(
                    location=[row["lat"], row["lon"]], radius=2, color="blue",
                    fill=True, fill_opacity=0.6,
                    popup=folium.Popup(
                        f"<b>Radio:</b> {row['radio']}<br><b>Net:</b> {row['net']}<br><b>Range:</b> {row['range']} m<br>",
                        max_width=250
                    )
                ).add_to(tower_group)

            tower_gdf = gpd.GeoDataFrame(
                filtered_towers,
                geometry=gpd.points_from_xy(filtered_towers.lon, filtered_towers.lat),
                crs="EPSG:4326"
            ).to_crs(epsg=3857)

            tower_gdf["range"] = tower_gdf["range"].fillna(0).clip(0, 5000)
            tower_gdf["geometry"] = tower_gdf.geometry.buffer(tower_gdf["range"])

            coverage = tower_gdf.geometry.union_all()
            coverage_gdf = gpd.GeoDataFrame(geometry=[coverage], crs="EPSG:3857").to_crs(epsg=4326)

            folium.GeoJson(
                coverage_gdf,
                style_function=lambda x: {
                    "fillColor": "blue", "color": "blue",
                    "weight": 1, "fillOpacity": 0.25, "interactive": False
                }
            ).add_to(tower_group)

    tower_group.add_to(mymap)

    # ----------------------------------------------------------
    # PUBLIC SERVICES
    # ----------------------------------------------------------
    with st.status("🏥 Kamu hizmetleri yükleniyor..."):
        try:
            public_tags = {
                "amenity": ["hospital", "school", "university", "police", "fire_station"]
            }
            public_gdf = ox.features.features_from_bbox((MIN_LON, MIN_LAT, MAX_LON, MAX_LAT), public_tags)

            hospital_layer   = folium.FeatureGroup(name="Hospitals",     show=False)
            school_layer     = folium.FeatureGroup(name="Schools",       show=False)
            university_layer = folium.FeatureGroup(name="Universities",  show=False)
            police_layer     = folium.FeatureGroup(name="Police",        show=False)
            fire_layer       = folium.FeatureGroup(name="Fire Stations", show=False)

            if not public_gdf.empty:
                public_gdf = public_gdf[public_gdf.geometry.notna()].to_crs(epsg=4326)

                def add_point_markers(gdf_subset, layer, color, label):
                    for _, row in gdf_subset.iterrows():
                        geom = row.geometry
                        name = row.get("name", "Unnamed")
                        if geom.geom_type == "Point":
                            pt = geom
                        elif geom.geom_type in ["Polygon", "MultiPolygon"]:
                            pt = geom.centroid
                        else:
                            continue
                        folium.CircleMarker(
                            location=[pt.y, pt.x], radius=5, color=color,
                            fill=True, fill_opacity=0.8, popup=f"{label}: {name}"
                        ).add_to(layer)

                add_point_markers(public_gdf[public_gdf["amenity"] == "hospital"],    hospital_layer,   "red",    "Hospital")
                add_point_markers(public_gdf[public_gdf["amenity"] == "school"],      school_layer,     "blue",   "School")
                add_point_markers(public_gdf[public_gdf["amenity"] == "university"],  university_layer, "purple", "University")
                add_point_markers(public_gdf[public_gdf["amenity"] == "police"],      police_layer,     "black",  "Police")
                add_point_markers(public_gdf[public_gdf["amenity"] == "fire_station"],fire_layer,       "orange", "Fire Station")

            st.write("✅ Kamu hizmetleri yüklendi.")

        except Exception as e:
            hospital_layer   = folium.FeatureGroup(name="Hospitals",     show=False)
            school_layer     = folium.FeatureGroup(name="Schools",       show=False)
            university_layer = folium.FeatureGroup(name="Universities",  show=False)
            police_layer     = folium.FeatureGroup(name="Police",        show=False)
            fire_layer       = folium.FeatureGroup(name="Fire Stations", show=False)
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
            "?service=WFS"
            "&version=2.0.0"
            "&request=GetFeature"
        )

        bbox_4326 = gpd.GeoSeries([box(MIN_LON, MIN_LAT, MAX_LON, MAX_LAT)], crs="EPSG:4326")
        bbox_3067 = bbox_4326.to_crs(epsg=3067)
        minx, miny, maxx, maxy = bbox_3067.total_bounds
        rail_bbox = f"{minx},{miny},{maxx},{maxy}"

        # Railway tracks
        try:
            railway_url = f"{rail_base_url}&typeNames=tn-ra:RailwayLink&bbox={rail_bbox},EPSG:3067"
            railway_gdf = gpd.read_file(railway_url)
            if not railway_gdf.empty:
                railway_gdf = railway_gdf.to_crs(epsg=4326)
                folium.GeoJson(
                    railway_gdf,
                    style_function=lambda feature: {"color": "black", "weight": 3, "opacity": 0.9},
                    tooltip=folium.GeoJsonTooltip(fields=["gml_id"], aliases=["Rail ID:"])
                ).add_to(rail_layer)
        except Exception as e:
            st.write(f"⚠️ Demiryolu hattı yüklenemedi: {e}")

        # Railway stations
        try:
            station_url = f"{rail_base_url}&typeNames=tn-ra:RailwayStationNode&bbox={rail_bbox},EPSG:3067"
            response = requests.get(station_url, timeout=60)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "xml")
            for pos in soup.find_all("gml:pos"):
                coords = pos.text.strip().split()
                if len(coords) >= 2:
                    point = gpd.GeoSeries.from_xy([float(coords[0])], [float(coords[1])], crs="EPSG:3067").to_crs(epsg=4326)
                    folium.CircleMarker(
                        location=[point.y.iloc[0], point.x.iloc[0]],
                        radius=5, color="red", fill=True, fill_opacity=0.9, popup="Railway Station"
                    ).add_to(station_layer)
        except Exception as e:
            st.write(f"⚠️ Tren istasyonları yüklenemedi: {e}")

        # Railway nodes
        try:
            node_url = f"{rail_base_url}&typeNames=tn-ra:RailwayNode&bbox={rail_bbox},EPSG:3067"
            response = requests.get(node_url, timeout=60)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "xml")
            for pos in soup.find_all("gml:pos"):
                coords = pos.text.strip().split()
                if len(coords) >= 2:
                    point = gpd.GeoSeries.from_xy([float(coords[0])], [float(coords[1])], crs="EPSG:3067").to_crs(epsg=4326)
                    folium.CircleMarker(
                        location=[point.y.iloc[0], point.x.iloc[0]],
                        radius=3, color="orange", fill=True, fill_opacity=0.7, popup="Railway Node"
                    ).add_to(node_layer)
        except Exception as e:
            st.write(f"⚠️ Demiryolu düğümleri yüklenemedi: {e}")

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

    legend_css = """
    <style>
    .leaflet-control { clear: both; }
    .leaflet-bottom.leaflet-right { right: auto !important; left: 10px !important; }
    </style>
    """
    mymap.get_root().header.add_child(folium.Element(legend_css))

    TreeLayerControl(
        overlay_tree={
            "label": "Layers",
            "children": [
                {"label": "Elevation",        "layer": contour_layer},
                {"label": "Population",       "layer": population_layer},
                {"label": "Cell Towers",      "layer": tower_group},
                {
                    "label": "Electricity",
                    "select_all_checkbox": True,
                    "children": [
                        {"label": "Lines",        "layer": line_layer},
                        {"label": "Substations",  "layer": substation_layer},
                        {"label": "Transformers", "layer": transformer_layer},
                        {"label": "Plants",       "layer": plant_layer},
                        {"label": "Catenary",     "layer": catenary_layer},
                        {"label": "Other",        "layer": other_layer},
                    ]
                },
                {
                    "label": "Public Services",
                    "select_all_checkbox": True,
                    "children": [
                        {"label": "Hospitals",    "layer": hospital_layer},
                        {"label": "Schools",      "layer": school_layer},
                        {"label": "Universities", "layer": university_layer},
                        {"label": "Police",       "layer": police_layer},
                        {"label": "Fire Stations","layer": fire_layer},
                    ]
                },
                {
                    "label": "Railways",
                    "select_all_checkbox": True,
                    "children": [
                        {"label": "Tracks",   "layer": rail_layer},
                        {"label": "Stations", "layer": station_layer},
                        {"label": "Nodes",    "layer": node_layer},
                    ]
                },
            ]
        },
        collapsed=False
    ).add_to(mymap)

    # ----------------------------------------------------------
    # RENDER MAP
    # ----------------------------------------------------------
    st.success("✅ Analiz tamamlandı! Harita aşağıda görüntüleniyor.")
    st_folium(mymap, width=None, height=750, returned_objects=[])

else:
    # Placeholder harita (boş, merkezi Finlandiya)
    st.info("👈 Soldaki panelden koordinatları gir ve **Analizi Başlat** butonuna tıkla.")
    placeholder_map = folium.Map(location=[60.2, 24.9], zoom_start=9, tiles="OpenStreetMap")
    st_folium(placeholder_map, width=None, height=500, returned_objects=[])
