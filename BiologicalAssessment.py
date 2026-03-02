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
from shapely.geometry import Polygon
from pyproj import Transformer
import pdfplumber

def extract_section(text, start_anchor, stop_anchor, skip_to=":"):
    if start_anchor in text:
        print(f"{start_anchor} section found.")
        start_match = re.search(rf"{start_anchor}", text)
        content_start = text.find(skip_to, start_match.end())+1
        stop_match = re.search(rf"{stop_anchor}", text)
        if start_match and stop_match:
            result = text[content_start:stop_match.start()]
            result = result.strip()
            print(result)
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


project_description = extract_section(text, "Project Description", "Facility Description", "\n")
proposed_improvement = extract_section(text, "Proposed Improvement", "Project Description", ":")
purpose_and_need = extract_section(text, "Purpose & Need", "Proposed Improvement", ":")
