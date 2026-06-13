from datetime import datetime
import os
import zipfile

import requests
from docx import Document
from docx.shared import Pt, RGBColor
from models import StepResult, BAField, FieldSource
from pyproj import Transformer
import shapely
from shapely.geometry import Polygon, shape
from xml.etree import ElementTree as ET
from species_config import resolve_tag_slug


def ingest_kmz(file_path):
    result = StepResult()

    if not os.path.isfile(file_path) or os.path.getsize(file_path) == 0:
        result.add_issue("KMZ file is missing or empty.")
        return result

    with zipfile.ZipFile(file_path, 'r') as kmz:
        kml_files = [f for f in kmz.namelist() if f.endswith('.kml')]
        if len(kml_files) == 0:
            result.add_issue("No KML file found in KMZ.")
            return result
        elif len(kml_files) > 1:
            result.add_issue("Multiple KML files found in KMZ.")
            return result
        with kmz.open(kml_files[0]) as kml:
            kml_data = kml.read()

    tree = ET.fromstring(kml_data)
    ns = "http://www.opengis.net/kml/2.2"
    coords_element = tree.find(f".//{{{ns}}}coordinates")

    if coords_element is None or not coords_element.text:
        result.add_issue("No coordinates found in KML file.")
        return result

    coord_strings = coords_element.text.split()
    coords = [(float(c.split(",")[0]), float(c.split(",")[1])) for c in coord_strings]
    project_polygon = shapely.Polygon(coords)

    if not project_polygon.is_valid:
        result.add_issue("Invalid geometry in KML file.")
        return result

    geojson_polygon = shapely.to_geojson(project_polygon)

    transformer = Transformer.from_crs("EPSG:4326", "EPSG:32614", always_xy=True)
    projected_coords = [transformer.transform(lon, lat) for lon, lat in coords]
    projected_polygon = Polygon(projected_coords)
    acres = round(projected_polygon.area / 4047, 2)

    result.fields['project_polygon'] = BAField(value=project_polygon, source=FieldSource.AUTO, tag='project_polygon')
    result.fields['geojson_polygon'] = BAField(value=geojson_polygon, source=FieldSource.AUTO, tag='geojson_polygon')
    result.fields['acres'] = BAField(value=acres, source=FieldSource.AUTO, tag='acres')

    return result


def query_ipac(geojson_polygon):
    result = StepResult()
    try:
        ipac_url = "https://ipac.ecosphere.fws.gov/location/api/resources"
        response = requests.post(
            ipac_url,
            json={"location.footprint": geojson_polygon, "timeout": 30, "includeOtherFwsResources": True}
        )

        if response.status_code != 200:
            result.add_issue(f"IPaC query failed with status code {response.status_code}.")
            return result

        ipac_data = response.json()
        result.fields['ipac_raw'] = BAField(value=ipac_data, source=FieldSource.AUTO, tag='ipac_raw')

        # TE Species
        species_list = []
        for _sid, species_info in ipac_data['resources']['populationsBySid'].items():
            species_list.append({
                "common_name": species_info['population']['optionalCommonName'],
                "scientific_name": species_info['population']['optionalScientificName'],
                "status": species_info['population']['listingStatusName'],
                "critical_habitat": species_info['crithabInFootprint'],
            })
        result.fields['te_species'] = BAField(value=species_list, source=FieldSource.AUTO, tag='te_species')

        # Wetlands
        wetland_data = ipac_data['resources']['wetlands']
        if wetland_data is None:
            result.add_issue("IPaC unable to return wetland data — NWI fallback required.")
        else:
            wetland_info = []
            for item in wetland_data['items']:
                wetland_info.append({
                    "wetland_area": item['acres'],
                    "wetland_name": item.get('wetlandType'),
                    "wetland_code": item.get('wetlandCode'),
                })
            result.fields['wetlands'] = BAField(value=wetland_info, source=FieldSource.AUTO, tag='wetlands')

        # Migratory Birds
        level_labels = {
            "BCC_RANGEWIDE_CON": "Bird of Conservation Concern (BCC) Range-wide Concern",
            "BCC_BCR_CON": "Bird of Conservation Concern (BCC) BCR Concern",
            "BCC_BCR": "Bird of Conservation Concern (BCC) BCR Concern",
            "NON_BCC_VULNERABLE": "Non-BCC Vulnerable",
            "NON_BCC_ESA": "Non-BCC ESA-Listed",
            "BCC_RANGEWIDE_PRV": "Bird of Conservation Concern (BCC) Range-wide Priority (Provisional)",
        }
        migbird_info = []
        for species in (ipac_data['resources']['migbirds'] or []):
            startdate = "Not given"
            enddate = "Not given"
            if species['optionalBreedsFrom'] is not None:
                startdate = datetime.strptime(species['optionalBreedsFrom'], "%Y-%m-%dT%H:%MZ").strftime("%B")
                enddate = datetime.strptime(species['optionalBreedsTo'], "%Y-%m-%dT%H:%MZ").strftime("%B")
            migbird_info.append({
                "common_name": species['phenologySpecies']['commonName'],
                "level_of_concern": level_labels.get((species.get('level') or {}).get('name', ''), "Not given"),
                "breeds_from": startdate,
                "breeds_to": enddate,
            })
        result.fields['migratory_birds'] = BAField(value=migbird_info, source=FieldSource.AUTO, tag='migratory_birds')

    except Exception as e:
        result.add_issue(f"Error querying IPaC: {str(e)}")

    return result


def generate_project_data_summary(ba, output_path: str):
    """
    Produce the Project Data Summary Word doc for the authoring biologist.
    Shows all AUTO-populated fields from the pipeline with their sources.
    ba: BiologicalAssessment instance with completed results.
    """
    result = StepResult()
    doc = Document()

    # Title
    title = doc.add_heading("Project Data Summary", level=1)
    title.runs[0].font.color.rgb = RGBColor(0x00, 0x38, 0x6B)  # ODOT navy

    # Metadata block
    meta = ba.metadata
    doc.add_heading("Project Information", level=2)
    info_table = doc.add_table(rows=3, cols=2)
    info_table.style = "Table Grid"
    _trow(info_table, 0, "JP Number", meta.jp_number)
    _trow(info_table, 1, "County", meta.county)
    _trow(info_table, 2, "Preparer", meta.preparer or "—")
    doc.add_paragraph()

    # Acreage
    kmz = ba.results.get('kmz_ingest')
    acres = kmz.fields['acres'].value if kmz and 'acres' in kmz.fields else "N/A"
    doc.add_heading("Project Footprint", level=2)
    doc.add_paragraph(f"Calculated acreage: {acres} ac  [AUTO — KMZ]")

    # TE Species
    ipac = ba.results.get('ipac')
    doc.add_heading("Threatened & Endangered Species (IPaC)", level=2)
    if ipac and 'te_species' in ipac.fields:
        species_list = ipac.fields['te_species'].value
        if species_list:
            tbl = doc.add_table(rows=1, cols=4)
            tbl.style = "Table Grid"
            hdr = tbl.rows[0].cells
            for i, h in enumerate(["Common Name", "Scientific Name", "Status", "Critical Habitat"]):
                hdr[i].text = h
                hdr[i].paragraphs[0].runs[0].bold = True
            for s in species_list:
                row = tbl.add_row().cells
                row[0].text = s.get('common_name') or "—"
                row[1].text = s.get('scientific_name') or "—"
                row[2].text = s.get('status') or "—"
                row[3].text = "Yes" if s.get('critical_habitat') else "No"
                # Flag unrecognized species
                if resolve_tag_slug(s.get('common_name') or "") is None:
                    result.add_issue(
                        f"Species not in template map: '{s.get('common_name')}' — "
                        "verify tag assignment before generating BA."
                    )
        else:
            doc.add_paragraph("No TE species returned by IPaC for this project footprint.")
    else:
        doc.add_paragraph("IPaC species data unavailable.")
    doc.add_paragraph()

    # Wetlands
    doc.add_heading("Wetlands", level=2)
    wetlands = ipac.fields.get('wetlands') if ipac else None
    nwi_used = 'nwi' in ba.results
    source_label = "NWI fallback" if nwi_used else "IPaC"
    if wetlands and wetlands.value:
        tbl = doc.add_table(rows=1, cols=2)
        tbl.style = "Table Grid"
        hdr = tbl.rows[0].cells
        hdr[0].text = "Name / Code"
        hdr[0].paragraphs[0].runs[0].bold = True
        hdr[1].text = "Acres"
        hdr[1].paragraphs[0].runs[0].bold = True
        for w in wetlands.value:
            row = tbl.add_row().cells
            row[0].text = w.get('wetland_name') or w.get('wetland_code') or w.get('nwi_code') or "—"
            area = w.get('wetland_area')
            row[1].text = str(area) if area is not None else "—"
        doc.add_paragraph(f"Source: {source_label}  [AUTO]")
    elif wetlands and not wetlands.value:
        doc.add_paragraph(f"No wetlands found within project footprint.  [AUTO — {source_label}]")
    else:
        doc.add_paragraph("Wetland data unavailable (IPaC and NWI both failed).")
    doc.add_paragraph()

    # Migratory Birds
    doc.add_heading("Migratory Birds of Conservation Concern (IPaC)", level=2)
    migbirds = ipac.fields.get('migratory_birds') if ipac else None
    if migbirds and migbirds.value:
        tbl = doc.add_table(rows=1, cols=3)
        tbl.style = "Table Grid"
        hdr = tbl.rows[0].cells
        for i, h in enumerate(["Common Name", "Level of Concern", "Breeding Window"]):
            hdr[i].text = h
            hdr[i].paragraphs[0].runs[0].bold = True
        for b in migbirds.value:
            row = tbl.add_row().cells
            row[0].text = b.get('common_name') or "—"
            row[1].text = b.get('level_of_concern') or "—"
            bf = b.get('breeds_from', 'Not given')
            bt = b.get('breeds_to', 'Not given')
            row[2].text = f"{bf} – {bt}" if bf != "Not given" else "Does not breed in project area"
        doc.add_paragraph("Source: IPaC  [AUTO]")
    elif migbirds:
        doc.add_paragraph("No migratory birds of conservation concern returned by IPaC.")
    else:
        doc.add_paragraph("Migratory bird data unavailable.")
    doc.add_paragraph()

    # Issues
    all_issues = ba.get_issues()
    if all_issues or result.issues:
        doc.add_heading("Issues / Flags", level=2)
        for issue in all_issues + result.issues:
            p = doc.add_paragraph(style="List Bullet")
            run = p.add_run(issue)
            run.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)

    # Footer note
    doc.add_paragraph()
    note = doc.add_paragraph(
        f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  "
        "All AUTO fields require biologist review before use in the final BA."
    )
    note.runs[0].font.size = Pt(8)
    note.runs[0].font.color.rgb = RGBColor(0x60, 0x60, 0x60)

    try:
        doc.save(output_path)
        result.fields['output_path'] = BAField(
            value=output_path, source=FieldSource.AUTO, tag='output_path'
        )
    except Exception as e:
        result.add_issue(f"Failed to save Project Data Summary: {e}")

    return result


def _trow(table, row_idx: int, label: str, value: str):
    """Helper: write a label/value pair into a two-column table row."""
    cells = table.rows[row_idx].cells
    cells[0].text = label
    cells[0].paragraphs[0].runs[0].bold = True
    cells[1].text = value


def query_nwi(geojson_polygon):
    """NWI REST MapServer fallback when IPaC cannot return wetland data."""
    result = StepResult()
    try:
        # Parse the GeoJSON string into a geometry dict for the NWI envelope query
        import json
        geom_dict = json.loads(geojson_polygon) if isinstance(geojson_polygon, str) else geojson_polygon
        poly = shape(geom_dict)
        bounds = poly.bounds  # (minx, miny, maxx, maxy)

        nwi_url = (
            "https://fwspublicservices.wim.usgs.gov/wetlandsmapservice/rest/services"
            "/Wetlands/MapServer/0/query"
        )
        envelope = {
            "xmin": bounds[0], "ymin": bounds[1],
            "xmax": bounds[2], "ymax": bounds[3],
            "spatialReference": {"wkid": 4326},
        }
        params = {
            "geometry": json.dumps(envelope),
            "geometryType": "esriGeometryEnvelope",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "ATTRIBUTE,ACRES,WETLAND_TYPE",
            "returnGeometry": "false",
            "f": "geojson",
        }
        response = requests.get(nwi_url, params=params, timeout=30)

        if response.status_code != 200:
            result.add_issue(f"NWI query failed with status code {response.status_code}.")
            return result

        nwi_data = response.json()
        features = nwi_data.get("features", [])
        wetland_info = []
        for feature in features:
            props = feature.get("properties", {})
            wetland_info.append({
                "wetland_name": props.get("WETLAND_TYPE", "Unknown"),
                "nwi_code": props.get("ATTRIBUTE", ""),
                "wetland_area": props.get("ACRES", None),
            })
        result.fields['wetlands'] = BAField(value=wetland_info, source=FieldSource.AUTO, tag='wetlands')

    except Exception as e:
        result.add_issue(f"Error querying NWI: {str(e)}")

    return result
