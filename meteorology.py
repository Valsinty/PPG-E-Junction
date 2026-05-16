import requests
import xml.etree.ElementTree as ET
from datetime import datetime

lat = 61.4981
lon = 23.7608

URL = (
    "https://opendata.fmi.fi/wfs"
    "?service=WFS"
    "&version=2.0.0"
    "&request=getFeature"
    "&storedquery_id="
    "fmi::forecast::harmonie::surface::point::multipointcoverage"
    "&latlon=" + str(lat) +"," + str(lon)
)

response = requests.get(URL)

root = ET.fromstring(response.content)

ns = {
    "gmlcov": "http://www.opengis.net/gmlcov/1.0",
    "gml": "http://www.opengis.net/gml/3.2"
}

# Get timestamps/positions
positions_text = root.find(
    ".//gmlcov:positions",
    ns
).text.strip()

positions = list(map(float, positions_text.split()))

triples = [
    positions[i:i+3]
    for i in range(0, len(positions), 3)
]

# Get weather data rows
tuples_text = root.find(
    ".//gml:doubleOrNilReasonTupleList",
    ns
).text.strip()

values = list(map(float, tuples_text.split()))

FIELD_COUNT = 21

rows = [
    values[i:i+FIELD_COUNT]
    for i in range(0, len(values), FIELD_COUNT)
]

# Column indices from DataRecord
TEMPERATURE_INDEX = 2
HUMIDITY_INDEX = 4
WIND_DIR_INDEX = 5
WIND_SPEED_INDEX = 6
TOTAL_CLOUD_INDEX = 10
VISIBILITY_INDEX = 19
WIND_GUST_INDEX = 20


results = []

for pos, row in zip(triples, rows):

    lat, lon, unix_time = pos

    timestamp = datetime.utcfromtimestamp(unix_time)

    temperature = row[TEMPERATURE_INDEX]
    humidity = row[HUMIDITY_INDEX]
    wind_dir = row[WIND_DIR_INDEX]
    wind_speed = row[WIND_SPEED_INDEX]
    total_cloud_cover = row[TOTAL_CLOUD_INDEX]
    visibility = row[VISIBILITY_INDEX]
    wind_gust = row[WIND_GUST_INDEX]

    results.append({
        "time": timestamp.isoformat(),
        "lat": lat,
        "lon": lon,
        "temp": temperature,
        "humidity": humidity,
        "wind_dir": wind_dir,
        "wind_speed": wind_speed,
        "cloud_cover": total_cloud_cover,
        "visibility": visibility,
        "wind_gust": wind_gust
    })

for r in results[:10]:
    print(r)


