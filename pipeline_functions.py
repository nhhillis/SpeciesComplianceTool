#Pipeline functions for the Biological Assessment Tool
#ingest_kmz: Function to ingest a KMZ file and extract the KML data with errors for empty kmz file, 
# more than one kml file, and invalid geometry. Returns a StepResult object with the extracted data 
# and any issues encountered during the process.

import os
import zipfile
from models import StepResult, BAField, FieldSource
from pyproj import Transformer
import shapely
from shapely.geometry import Polygon
from xml.etree import ElementTree as ET


def ingest_kmz(file_path):
    result = StepResult()
    
    #Check if the file is a present and is not empty, if not, add an issue to the result and return it.
    if not os.path.isfile(file_path) or os.path.getsize(file_path) == 0:
        result.add_issue("KMZ file is missing or empty.")
        return result
    
    #check if there is more than one kml file in the kmz, if so, add an issue to the result and return it.
    with zipfile.ZipFile(file_path, 'r') as kmz:
        kml_files = [f for f in kmz.namelist() if f.endswith('.kml')]
        if len(kml_files) == 0:
            result.add_issue("No KML file found in KMZ.")
            return result
        elif len(kml_files) > 1:
            result.add_issue("Multiple KML files found in KMZ.")
            return result
        kml_file = kml_files[0]
        with kmz.open(kml_file) as kml:
            kml_data = kml.read()

    #if that all works, return the project_polygon, geojson_polygon, and acres.      
    #parsing kml_data into a tree structure
    tree = ET.fromstring(kml_data)

    #assigning the url (namespace) into variable for simplicity
    ns = "http://www.opengis.net/kml/2.2" 

    #f"..." {f string} inserts the url (ns) 
    coords_element = tree.find(f".//{{{ns}}}coordinates")
    
    #splits the coordinates based on whitespace. Gives us the coordinates for each point of the polygon, seperated by commmas.
    coord_strings = coords_element.text.split()

    #splits coord_strings by "," and only selects the lat and long, converts to float
    coords = [(float(c.split(",")[0]), float(c.split(",")[1])) for c in coord_strings]
    
    #create a shapely polygon and pass the coordinates generated above
    project_polygon = shapely.Polygon(coords)

    #convert shapely polygon to geojson format,  to a GeoJSON object for IPaC .
    geojason_polygon = shapely.to_geojson(project_polygon)

    #check if the geometry is valid, if not, add an issue to the result and return it.
    if not project_polygon.is_valid:
        result.add_issue("Invalid geometry in KML file.")
        return result

    #converts coordinates from wgs84(4326) to UTM zone 14n (32614), longitude is first lattitude is second
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:32614", always_xy=True)
    
    #Reproject coordinates 
    projected_coords = [transformer.transform(lon, lat) for lon, lat in coords]

    #create a shapely polygon from reprojected coordinates
    projected_polygon = Polygon(projected_coords)

    #extract area property from shapely polygon
    area_sq_meters = projected_polygon.area

    #convert to acres 
    acres = area_sq_meters/4047
    acres = round(acres,2)

    #add the project_polygon, geojson_polygon, and acres to the result fields
    result.fields['project_polygon'] = BAField(value=project_polygon, source=FieldSource.AUTO, tag='project_polygon')
    result.fields['geojson_polygon'] = BAField(value=geojason_polygon, source=FieldSource.AUTO, tag='geojson_polygon')
    result.fields['acres'] = BAField(value=acres, source=FieldSource.AUTO, tag='acres')
    
    return result