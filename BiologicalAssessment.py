#  This tool assists in the gathering of data and writing of biological assessments, particularly
#  for Oklahoma Department of Transportation projects. Inputs would include a KMZ of the project 
#  footprint, initiation reports, scope meeting minutes.  A scope of work and document preparation 
#  guidance will also be incorperated. 
#  
#  
#  Step 1: Get inputs
#   1a. KMZ file
#         - Polygon naming convention: "[County] JP [number] - Project Footprint"
#         - e.g. "McClain JP 38881(04) - Project Footprint"
#         - Extract: polygon coordinates, county, JP number, calculated acreage
#         - Store as Shapely polygon for spatial queries

#   1b. PDF inputs (one or more of the following document types)
#         - Project Initiation Report  ← primary source for sections below
#         - Bridge Inspection Reports
#         - Scope Meeting Minutes

#   1c. PDF text extraction — DRAFT CONTENT ONLY
#         - Target: the labeled box/form fields in the Project Initiation Report
#         - Sections: "Project Description", "Existing Conditions", "Proposed Improvements"
#         - IMPORTANT: extracted text is a STARTING POINT only
#         - Final language requires additional sources + client input
#         - Tool should flag this clearly in output so user remembers to review

import re
import zipfile
import tempfile
import os
from tkinter import filedialog as fd
from xml.etree import ElementTree as ET
import shapely
from shapely.geometry import Polygon
from pyproj import Transformer
import pdfplumber
import requests
import json
from datetime import datetime 

# This function takes in the full text of a PDF, along with start and stop anchors to identify the section of interest. It also has an optional parameter to skip to a specific character (like ":") if needed. The function returns the extracted section of text, or prints a message if the section is not found.
def extract_section(text, start_anchor, stop_anchor, skip_to=":"):
    if start_anchor in text:
        print(f"{start_anchor} section found.")
        start_match = re.search(rf"{start_anchor}", text)
        content_start = text.find(skip_to, start_match.end())+1
        stop_match = re.search(rf"{stop_anchor}", text)
        if start_match and stop_match:
            result = text[content_start:stop_match.start()]
            result = result.strip()
            #print(start_anchor, " - ", result)
            return result
        else:
            print(f"{start_anchor} not found in text. Open in Bluebeam and use OCR to extract text. Save, and re-run this tool to extract text from the OCR layer.")
    else:
        print(f"{start_anchor} section not found. Open in Bluebeam and use OCR to extract text. Save, and re-run this tool to extract text from the OCR layer.")


###ask to open kmz
kmz_path = fd.askopenfilename(filetypes=[("KMZ files", "*.kmz")])

#creates temp file path
with tempfile.TemporaryDirectory() as tmpdir:
    
    #unzips kmz, extracts doc.kml into tmpdir
    with zipfile.ZipFile(kmz_path, "r") as kmz:
        kmz.extract("doc.kml", tmpdir)
    
    #build full path to extracted doc.kml
    kml_path = os.path.join(tmpdir, 'doc.kml')
    
    #kml is opened and read as kml_data
    with open(kml_path, "r") as kml_file:
        kml_data = kml_file.read()
    
    #filename is extracted from filepath, .kmz is removed, JP no. and county are extracted from filename
    filename = os.path.basename(kmz_path)
    filename = os.path.splitext(filename)[0]
    elements = filename.split(" ")
    jp = elements[2]
    county = elements[0]
    
    #parsing kml_data into a tree structure
    tree = ET.fromstring(kml_data)

    #assigning the url (namespace) into variable for simplicity
    ns = "http://www.opengis.net/kml/2.2" 

    #f"..." {f string} inserts the url (ns) 
    placemark = tree.find(f".//{{{ns}}}Placemark")
    coords_element = tree.find(f".//{{{ns}}}coordinates")
    
    #splits the coordinates based on whitespace. Gives us the coordinates for each point of the polygon, seperated by commmas.
    coord_strings = coords_element.text.split()

    #splits coord_strings by "," and only selects the lat and long, converts to float
    coords = [(float(c.split(",")[0]), float(c.split(",")[1])) for c in coord_strings]
    
    #create a shapely polygon and pass the coordinates generated above
    project_polygon = Polygon(coords)

    #convert shapely polygon to geojson format,  to a GeoJSON object for IPaC .
    geojason_polygon = shapely.to_geojson(project_polygon)

    try:
        #IPaC API endpoint for species list based on a polygon
        ipac_url = "https://ipac.ecosphere.fws.gov/location/api/resources"

        #IPaC API request with the GeoJSON polygon as the payload
        response = requests.post(ipac_url, json={"location.footprint": geojason_polygon, "timeout": 30, "includeOtherFwsResources": True})

        #Check if the request was successful
        if response.status_code == 200:
            ipac_data= response.json()
            #print(json.dumps(ipac_data, indent=2))  # Print the entire response for debugging
            #print(ipac_data['resources'].keys())
            #print(ipac_data['resources']['wetlandsQueried'])
            #print(ipac_data['resources']['wetlands'])
            print("Successfully retrieved data from IPaC API.")
            
            #gets wetland data from the response, which is nested under 'resources' and 'wetlands' Need acres/name/boundaries
            wetland_data = ipac_data['resources']['wetlands'] 
            #checking if IPAC is returning None, meaning it is unable to access NWI data
            #Then checking if the 'items' key in the wetland data is empty, meaning there are no wetlands in the project area. 
            # If there is wetland data, it prints the acres, name, and boundaries of the wetlands.
            if wetland_data is None:
                print("IPAC unable to return wetland data.")
            elif not wetland_data['items']:
                print("No wetland data found for this location.")
            else:
                print("Wetland Acres:", wetland_data['items']['acres'])
                print("Wetland Name:", wetland_data['items']['name'])
                print("Wetland boundaries:", wetland_data['items']['bounds'])

            #gets species data from the response, which is nested under 'resources' and 'populationsBySid' Need wetlands/crithab/sci name
            species_data = ipac_data['resources']['populationsBySid']  
            # Loop through the species data and print the optional common name, scientific name, listing status, and whether critical habitat is in the project footprint. This information is nested under 'population' for each species.
            for optionalCommonName, species_info in species_data.items():
                print(f"Species: {species_info['population']['optionalCommonName']}")
                print(f"Scientific Name: {species_info['population']['optionalScientificName']}")
                print(f"Status: {species_info['population']['listingStatusName']}")
                print(f"Critical Habitat: {species_info['crithabInFootprint']}")

            # extract migratory bird data.
            migbird_data = ipac_data['resources']['migbirds']
            if not migbird_data:
                print("No migratory bird data found for this location.")
            else:
                print("Migratory Bird Species in Project Area:")
                for species in migbird_data:
                    print(f"Common Name: {species['phenologySpecies']['commonName']}")
                    #dict containing meanings of the different levels of concern for migratory birds, which are returned in the IPaC response as codes. The code is used to look up the corresponding level of concern and print it in a more understandable format.
                    level_name = {"BCC_RANGEWIDE_CON": "Bird of Conservation Concern (BCC) Range-wide Concern", 
                                  "BCC_BCR_CON": "Bird of Conservation Concern (BCC) BCR Concern",
                                  "NON_BCC_VULNERABLE": "Non-BCC Vulnerable",
                                  "BCC_RANGEWIDE_PRV": "Bird of Conservation Concern (BCC) Range-wide Priority (Provisional)"}
                    if species['level']['name'] not in level_name:
                        print(f"Level of Concern: not given in IPaC response")
                    else:
                        print(f"Level of Concern: {level_name[species['level']['name']]}")
                    if species['optionalBreedsFrom'] is None:
                        print("Does not breed in project area.")
                    else:
                        startdate = datetime.strptime(species['optionalBreedsFrom'], "%Y-%m-%dT%H:%MZ").strftime("%B")
                        enddate = datetime.strptime(species['optionalBreedsTo'], "%Y-%m-%dT%H:%MZ").strftime("%B")
                        print(f"Breeds From: {startdate}")
                        print(f"Breeds To: {enddate}")
        else:
            print(f"Failed to retrieve species list. Status code: {response.status_code}")
    except Exception as e:
        print(f"An error occurred while connecting to the IPaC API: {e}")

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

#defining the pdf file paths, user can select multiple pdfs but only the first one will be used for text extraction in this draft version
pdf_paths = fd.askopenfilenames(filetypes=[("PDF files", "*.pdf")])

#Extracting text from the selected PDF file using pdfplumber
with pdfplumber.open(pdf_paths[0]) as pdf_pages:
    text = ""
    for page in pdf_pages.pages:
        text += page.extract_text()

#extracting the sections of interest from the text using the extract_section function defined above. The function looks for the start and stop anchors to identify the section, and can also skip to a specific character (like ":") if needed. The extracted sections are printed to the console for review.
project_description = extract_section(text, "Project Description", "Facility Description", "\n")
proposed_improvement = extract_section(text, "Proposed Improvement", "Project Description", ":")
purpose_and_need = extract_section(text, "Purpose & Need", "Proposed Improvement", ":")

