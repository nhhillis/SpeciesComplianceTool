#Pipeline functions for the Biological Assessment Tool
#ingest_kmz: Function to ingest a KMZ file and extract the KML data with errors for empty kmz file, 
# more than one kml file, and invalid geometry. Returns a StepResult object with the extracted data 
# and any issues encountered during the process.

from datetime import datetime
import os
import zipfile

import requests
from models import StepResult, BAField, FieldSource, add_issue
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

def query_ipac(geojson_polygon):
    #returns BAField objects for TE species, wetlands, and migratory birds. Each StepResult contains the relevant fields and any issues encountered during the query process.    
    result = StepResult()
    try:
        ipac_url ="https://ipac.ecosphere.fws.gov/location/api/resources"
        response = requests.post(ipac_url, json={"location.footprint": geojson_polygon, "timeout": 30, "includeOtherFwsResources": True})
        if response.status_code == 200:
            ipac_data = response.json()
            ##########################TESpecies#############################
            species_data = ipac_data['resources']['populationsBySid'] 
            #looping through the species data and adding it to the result fields as BAField objects
            species_list = []
            for optionalCommonName, species_info in species_data.items():
                species_list.append({
                    "common_name": optionalCommonName,
                    "scientific_name": species_info['population']['optionalScientificName'],
                    "status": species_info['population']['listingStatusName'],
                    "critical_habitat": species_info['crithabInFootprint']
                })
            result.fields['te_species'] = BAField(value=species_list, source=FieldSource.AUTO, tag='te_species')

           #####################WetlandData################################################################################
           
            wetland_data = ipac_data['resources']['wetlands']
            wetland_info = []
            if wetland_data is None:
                    result.add_issue(f"IPAC unable to return wetland data.")
                    #NWI Backup API call if IPaC fails to return wetland data.
                    return result

            else:
                    for items in wetland_data['items']:
                        wetland_info.append({
                            "wetland_area": items['acres'],
                            "wetland_name": items['name']   ,
                            "wetland_boundaries": items['bounds']
                        })
            result.fields['wetlands'] = BAField(value=wetland_info, source=FieldSource.AUTO, tag='wetlands')
            
            #############################migratory birds#############################

            migbird_data = ipac_data['resources']['migbirds']
            migbird_info = []
            for species in migbird_data:
                
                level_name = {"BCC_RANGEWIDE_CON": "Bird of Conservation Concern (BCC) Range-wide Concern", 
                                  "BCC_BCR_CON": "Bird of Conservation Concern (BCC) BCR Concern",
                                  "NON_BCC_VULNERABLE": "Non-BCC Vulnerable",
                                  "BCC_RANGEWIDE_PRV": "Bird of Conservation Concern (BCC) Range-wide Priority (Provisional)"}
                if species['level']['name'] not in level_name:                        
                    print(f"Level of Concern: not given in IPaC response")
                else:
                        print(f"Level of Concern: {level_name[species['level']['name']]}")
                
                startdate = "Not given"
                enddate = "Not given"
                
                if species['optionalBreedsFrom'] is None:
                        print("Does not breed in project area.")
                else:
                    startdate = datetime.strptime(species['optionalBreedsFrom'], "%Y-%m-%dT%H:%MZ").strftime("%B")
                    enddate = datetime.strptime(species['optionalBreedsTo'], "%Y-%m-%dT%H:%MZ").strftime("%B")
                    print(f"Breeds From: {startdate}")
                    print(f"Breeds To: {enddate}")
                    
                migbird_info.append({
                    "common_name": species['phenologySpecies']['commonName'],
                    "level_of_concern": level_name.get(species['level']['name'], "Not given"),
                    "breeds_from": startdate,
                    "breeds_to": enddate 
                })
                
                

            result.fields['migratory_birds'] = BAField(value=migbird_info, source=FieldSource.AUTO, tag='migratory_birds')

        else:
            result.add_issue(f"IPaC query failed with status code {response.status_code}.")
            return result
    
    except Exception as e:
       result.add_issue(f"Error querying IPaC: {str(e)}")
       return result
            
            
