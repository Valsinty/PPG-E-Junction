import os
import json
import geopandas as gpd
from google.oauth2.service_account import Credentials
def get_elevation_from_corners(min_longitude, min_latitude, max_longitude, max_latitude):
  # 1. Verify the credentials file exists
  if not os.path.exists("credentials.json"):
      raise FileNotFoundError("Missing credentials.json file!")
  
  # 2. Load the Service Account details
  with open("credentials.json", "r") as f:
      creds_dict = json.load(f)
  
  # 3. Create auth credentials for streaming
  credentials = Credentials.from_service_account_info(creds_dict)
  
  # 4. Insert your actual Google Drive file ID
  # Formatted as: ://google.com
  file_id = "1jXSLvqrgHSuJ3lWKVqyvTh1B3L_klbMt"
  
  # 5. Connect to Google Drive over the cloud network
  # We pass the credentials directly to the storage options
  gdrive_url = f"gdrive://{file_id}"
  storage_options = {"gdrive": {"credentials": credentials}}
  
  # 6. Define a bounding box to query just a small region of the 20 GB file
  # Format: (min_longitude, min_latitude, max_longitude, max_latitude)
  roi_bbox = (min_longitude, min_latitude, max_longitude, max_latitude)
  
  print("Streaming requested spatial data chunk from Google Drive...")
  gdf = gpd.read_file(gdrive_url, bbox=roi_bbox, storage_options=storage_options)
  
  # 7. Use your data
  print(f"Successfully fetched {len(gdf)} rows from the GPKG file!")
  return gdf
__all__ = ['get_elevation_from_corners']
