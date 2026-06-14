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
import ecoregion_data
import cg_soils_data


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
    Single output document for both the authoring biologist and QA/QC reviewer.
    Shows all AUTO-populated fields with source attribution and any flagged issues.
    """
    result = StepResult()
    doc = Document()
    run_date = datetime.now().strftime('%Y-%m-%d %H:%M')

    RED = RGBColor(0xC0, 0x00, 0x00)
    GREEN = RGBColor(0x57, 0xB8, 0x47)  # Olsson brand green
    GRAY = RGBColor(0x60, 0x60, 0x60)

    # Set Arial as document default font
    doc.styles['Normal'].font.name = 'Arial'
    for style_name in ('Heading 1', 'Heading 2', 'Heading 3', 'List Bullet'):
        try:
            doc.styles[style_name].font.name = 'Arial'
        except KeyError:
            pass

    def _h(text, level):
        p = doc.add_heading(text, level=level)
        for run in p.runs:
            run.font.name = 'Arial'
            run.font.color.rgb = GREEN
        return p

    def _source_line(source_label, issues=None):
        p = doc.add_paragraph()
        run = p.add_run(f"Source: {source_label}  [AUTO]")
        run.font.size = Pt(9)
        run.font.color.rgb = GRAY
        if issues:
            for issue in issues:
                p2 = doc.add_paragraph(style="List Bullet")
                r2 = p2.add_run(f"FLAG: {issue}")
                r2.font.color.rgb = RED
                r2.font.size = Pt(9)

    # Title
    _h("Project Data Summary", level=1)

    # Metadata
    meta = ba.metadata
    _h("Project Information", level=2)
    info_table = doc.add_table(rows=3, cols=2)
    info_table.style = "Table Grid"
    _trow(info_table, 0, "JP Number", meta.jp_number)
    _trow(info_table, 1, "County", meta.county)
    _trow(info_table, 2, "Preparer", meta.preparer or "—")
    doc.add_paragraph()

    # Pipeline Step Summary
    _h("Pipeline Step Summary", level=2)
    step_table = doc.add_table(rows=1, cols=3)
    step_table.style = "Table Grid"
    hdr = step_table.rows[0].cells
    for i, h in enumerate(["Step", "Status", "Issues"]):
        hdr[i].text = h
        hdr[i].paragraphs[0].runs[0].bold = True
    step_labels = {
        'kmz_ingest': 'KMZ Ingest',
        'ipac': 'IPaC Query',
        'nwi': 'NWI Fallback',
        'ssurgo': 'SSURGO Soils',
        'mlra': 'MLRA / Carter & Gregory Soils',
        'nhd': 'NHD Streams',
        'ecoregion': 'Ecoregion (Woods et al. 2005)',
    }
    for step_name, step_result in ba.results.items():
        if step_name == 'project_data_summary':
            continue
        row = step_table.add_row().cells
        row[0].text = step_labels.get(step_name, step_name)
        row[1].text = step_result.status.upper()
        if step_result.issues:
            row[1].paragraphs[0].runs[0].font.color.rgb = RED
        row[2].text = "; ".join(step_result.issues) if step_result.issues else "None"
    doc.add_paragraph()

    # Project Footprint
    kmz = ba.results.get('kmz_ingest')
    acres = kmz.fields['acres'].value if kmz and 'acres' in kmz.fields else None
    _h("Project Footprint", level=2)
    doc.add_paragraph(f"Calculated acreage: {acres} ac" if acres is not None else "Acreage unavailable.")
    _source_line("KMZ geometry — EPSG:32614 projected area", kmz.issues if kmz else ["KMZ step failed"])

    # TE Species
    ipac = ba.results.get('ipac')
    _h("Threatened & Endangered Species", level=2)
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
                if resolve_tag_slug(s.get('common_name') or "") is None:
                    result.add_issue(
                        f"Species not in template map: '{s.get('common_name')}' — "
                        "verify tag assignment before generating BA."
                    )
        else:
            doc.add_paragraph("No TE species returned by IPaC for this project footprint.")
    else:
        doc.add_paragraph("IPaC species data unavailable.")
    _source_line("IPaC Location API — populationsBySid", ipac.issues if ipac else ["IPaC step failed"])

    # Wetlands
    nwi_used = 'nwi' in ba.results
    wetland_source = "NWI REST MapServer (IPaC fallback)" if nwi_used else "IPaC Location API"
    wetlands = ipac.fields.get('wetlands') if ipac else None
    nwi_issues = ba.results['nwi'].issues if nwi_used else []
    _h("Wetlands", level=2)
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
    elif wetlands:
        doc.add_paragraph("No wetlands found within project footprint.")
    else:
        doc.add_paragraph("Wetland data unavailable.")
    _source_line(wetland_source, nwi_issues or (ipac.issues if ipac else []))

    # Migratory Birds
    migbirds = ipac.fields.get('migratory_birds') if ipac else None
    _h("Migratory Birds of Conservation Concern", level=2)
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
    elif migbirds:
        doc.add_paragraph("No migratory birds of conservation concern returned by IPaC.")
    else:
        doc.add_paragraph("Migratory bird data unavailable.")
    _source_line("IPaC Location API — migbirds")

    # Soils
    ssurgo = ba.results.get('ssurgo')
    soils = ssurgo.fields.get('soils') if ssurgo else None
    _h("Soils (SSURGO)", level=2)
    if soils and soils.value:
        tbl = doc.add_table(rows=1, cols=4)
        tbl.style = "Table Grid"
        hdr = tbl.rows[0].cells
        for i, h in enumerate(["Map Unit", "Hydric Rating", "Drainage Class", "Farmland Class"]):
            hdr[i].text = h
            hdr[i].paragraphs[0].runs[0].bold = True
        for s in soils.value:
            row = tbl.add_row().cells
            row[0].text = s.get('map_unit_name') or "—"
            row[1].text = s.get('hydric_rating') or "—"
            row[2].text = s.get('drainage_class') or "—"
            row[3].text = s.get('farmland_class') or "—"
    elif soils:
        doc.add_paragraph("No soil map units found within project footprint.")
    else:
        doc.add_paragraph("Soils data unavailable.")
    _source_line("USDA SSURGO / Soil Data Access", ssurgo.issues if ssurgo else ["SSURGO step failed"])

    # Carter & Gregory Soils
    mlra_result = ba.results.get('mlra')
    mlra_data = mlra_result.fields.get('mlra').value if (mlra_result and 'mlra' in mlra_result.fields) else None
    _h("Soils — Regional Context (Carter & Gregory 2008)", level=2)
    if mlra_data:
        doc.add_paragraph(f"MLRA {mlra_data['mlra_sym']} — {mlra_data['mlra_name']}")
        assocs = mlra_data.get('associations', [])
        if assocs:
            tbl = doc.add_table(rows=1, cols=4)
            tbl.style = "Table Grid"
            hdr = tbl.rows[0].cells
            for i, h in enumerate(["Unit", "Soil Association", "Soil Orders", "Description"]):
                hdr[i].text = h
                hdr[i].paragraphs[0].runs[0].bold = True
            for a in assocs:
                row = tbl.add_row().cells
                row[0].text = str(a.get('unit', '—'))
                row[1].text = a.get('association') or '—'
                row[2].text = a.get('orders') or '—'
                row[3].text = a.get('description') or '—'
        else:
            doc.add_paragraph("No Carter & Gregory associations found for this MLRA.")
    elif mlra_result:
        doc.add_paragraph("MLRA / Carter & Gregory data unavailable.")
    else:
        doc.add_paragraph("MLRA step did not run.")
    _source_line(
        "NRCS MLRA Feature Service + Carter & Gregory 2008, Soil Map of Oklahoma",
        mlra_result.issues if mlra_result else ["MLRA step failed"],
    )

    # NHD Streams
    nhd_result = ba.results.get('nhd')
    streams = nhd_result.fields.get('streams') if nhd_result else None
    _h("Stream Features (NHD)", level=2)
    if streams and streams.value:
        tbl = doc.add_table(rows=1, cols=3)
        tbl.style = "Table Grid"
        hdr = tbl.rows[0].cells
        for i, h in enumerate(["Name", "Type", "Length (mi)"]):
            hdr[i].text = h
            hdr[i].paragraphs[0].runs[0].bold = True
        for s in streams.value:
            row = tbl.add_row().cells
            row[0].text = s.get('name') or "—"
            row[1].text = s.get('type') or "—"
            row[2].text = str(s.get('length_mi', "—"))
    elif streams:
        doc.add_paragraph("No stream features found within project footprint.")
    else:
        doc.add_paragraph("NHD stream data unavailable.")
    _source_line("USGS National Hydrography Dataset — Large Scale Flowline", nhd_result.issues if nhd_result else ["NHD step failed"])

    # Ecoregion
    eco_result = ba.results.get('ecoregion')
    eco = eco_result.fields.get('ecoregion').value if (eco_result and 'ecoregion' in eco_result.fields) else None
    _h("Ecoregion (Woods et al. 2005)", level=2)
    if eco:
        eco_table = doc.add_table(rows=7, cols=2)
        eco_table.style = "Table Grid"
        _trow(eco_table, 0, "Level IV Ecoregion", f"{eco['code'].upper()} — {eco['name']}")
        _trow(eco_table, 1, "Level III Ecoregion", eco['level_iii'] or "—")
        _trow(eco_table, 2, "Mean Annual Precipitation", f"{eco['precip_in']} inches" if eco['precip_in'] else "—")
        _trow(eco_table, 3, "Growing Season (Frost-Free)", f"{eco['frost_free_days']} days" if eco['frost_free_days'] else "—")
        _trow(eco_table, 4, "Mean January Temp (min/max °F)", eco['temp_jan'] or "—")
        _trow(eco_table, 5, "Mean July Temp (min/max °F)", eco['temp_jul'] or "—")
        _trow(eco_table, 6, "Land Cover and Land Use", eco['land_use'] or "—")
    elif eco_result:
        doc.add_paragraph("Ecoregion data unavailable.")
    else:
        doc.add_paragraph("Ecoregion step did not run.")
    _source_line(
        "EPA Level IV Ecoregion GIS Service + Woods et al. 2005 reference table",
        eco_result.issues if eco_result else ["Ecoregion step failed"],
    )

    # Issues Log
    all_issues = ba.get_issues() + result.issues
    _h("Issues / Flags", level=2)
    if all_issues:
        for issue in all_issues:
            p = doc.add_paragraph(style="List Bullet")
            run = p.add_run(issue)
            run.font.color.rgb = RED
    else:
        doc.add_paragraph("No issues recorded.")

    # Footer
    doc.add_paragraph()
    note = doc.add_paragraph(
        f"Generated {run_date}  |  All AUTO fields require biologist review before use in the final BA."
    )
    note.runs[0].font.size = Pt(8)
    note.runs[0].font.color.rgb = GRAY

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


def query_mlra(geojson_polygon):
    """Query NRCS MLRA service for project centroid, then look up Carter & Gregory 2008 associations."""
    result = StepResult()
    try:
        import json
        geom_dict = json.loads(geojson_polygon) if isinstance(geojson_polygon, str) else geojson_polygon
        poly = shape(geom_dict)
        centroid = poly.centroid

        params = {
            "geometry": json.dumps({"x": centroid.x, "y": centroid.y, "spatialReference": {"wkid": 4326}}),
            "geometryType": "esriGeometryPoint",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "MLRARSYM,MLRA_NAME",
            "returnGeometry": "false",
            "f": "json",
        }
        response = requests.get(
            "https://services.arcgis.com/SXbDpmb7xQkk44JV/arcgis/rest/services/US_MLRA/FeatureServer/0/query",
            params=params,
            timeout=30,
        )
        if response.status_code != 200:
            result.add_issue(f"MLRA query failed with status code {response.status_code}.")
            return result

        data = response.json()
        if data.get("error"):
            result.add_issue(f"MLRA query error: {data['error'].get('message', 'Unknown error')}.")
            return result

        features = data.get("features", [])
        if not features:
            result.add_issue("No MLRA feature returned for project centroid.")
            return result

        attrs = features[0]["attributes"]
        mlra_sym = (attrs.get("MLRARSYM") or "").strip()
        mlra_name = (attrs.get("MLRA_NAME") or "").strip()

        associations = cg_soils_data.lookup(mlra_sym)
        if associations is None:
            result.add_issue(
                f"MLRA '{mlra_sym}' ({mlra_name}) not found in Carter & Gregory 2008 reference table."
            )

        result.fields['mlra'] = BAField(
            value={
                "mlra_sym": mlra_sym,
                "mlra_name": mlra_name,
                "associations": associations or [],
            },
            source=FieldSource.AUTO,
            tag='mlra',
        )

    except Exception as e:
        result.add_issue(f"Error querying MLRA: {str(e)}")

    return result


def query_ecoregion(geojson_polygon):
    """
    Query EPA Level IV ecoregion for the project centroid, then look up
    climate and land use data from the Woods et al. 2005 reference table.
    """
    result = StepResult()
    try:
        import json
        geom_dict = json.loads(geojson_polygon) if isinstance(geojson_polygon, str) else geojson_polygon
        poly = shape(geom_dict)
        centroid = poly.centroid

        base_url = "https://geodata.epa.gov/arcgis/rest/services/ORD/USEPA_Ecoregions_Level_III_and_IV/MapServer"
        params = {
            "geometry": json.dumps({"x": centroid.x, "y": centroid.y, "spatialReference": {"wkid": 4326}}),
            "geometryType": "esriGeometryPoint",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "US_L4CODE,US_L4NAME,US_L3NAME",
            "returnGeometry": "false",
            "f": "json",
        }

        response = requests.get(f"{base_url}/7/query", params=params, timeout=30)
        if response.status_code != 200:
            result.add_issue(f"Ecoregion query failed with status code {response.status_code}.")
            return result

        data = response.json()
        features = data.get("features", [])
        if not features:
            result.add_issue("No ecoregion feature returned for project centroid.")
            return result

        attrs = features[0]["attributes"]
        code = (attrs.get("US_L4CODE") or "").strip().lower()
        gis_name = attrs.get("US_L4NAME") or ""
        level_iii = attrs.get("US_L3NAME") or ""

        eco = ecoregion_data.lookup(code)
        if eco is None:
            result.add_issue(
                f"Ecoregion code '{code}' ({gis_name}) not found in Woods et al. 2005 reference table."
            )
            result.fields['ecoregion'] = BAField(
                value={
                    "code": code,
                    "name": gis_name,
                    "level_iii": level_iii,
                    "precip_in": None,
                    "frost_free_days": None,
                    "temp_jan": None,
                    "temp_jul": None,
                    "land_use": None,
                },
                source=FieldSource.AUTO,
                tag='ecoregion',
            )
            return result

        result.fields['ecoregion'] = BAField(
            value={
                "code": code,
                "name": eco["name"],
                "level_iii": eco["level_iii"],
                "precip_in": eco["precip_in"],
                "frost_free_days": eco["frost_free_days"],
                "temp_jan": eco["temp_jan"],
                "temp_jul": eco["temp_jul"],
                "land_use": eco["land_use"],
            },
            source=FieldSource.AUTO,
            tag='ecoregion',
        )

    except Exception as e:
        result.add_issue(f"Error querying ecoregion: {str(e)}")

    return result


def query_nhd(geojson_polygon):
    """Query USGS NHD Large Scale Flowline layer for stream features within the project footprint."""
    result = StepResult()
    try:
        import json
        geom_dict = json.loads(geojson_polygon) if isinstance(geojson_polygon, str) else geojson_polygon
        poly = shape(geom_dict)
        bounds = poly.bounds

        fcode_labels = {
            46006: "Perennial",
            46003: "Intermittent",
            46007: "Ephemeral",
            33600: "Canal/Ditch",
            55800: "Canal/Ditch",
            46000: "Stream/River",
        }

        envelope = {
            "xmin": bounds[0], "ymin": bounds[1],
            "xmax": bounds[2], "ymax": bounds[3],
            "spatialReference": {"wkid": 4326},
        }
        params = {
            "geometry": json.dumps(envelope),
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "where": "fcode IN (46006,46003,46007,33600,55800,46000)",
            "outFields": "gnis_name,fcode,lengthkm",
            "returnGeometry": "false",
            "f": "json",
        }
        response = requests.get(
            "https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer/6/query",
            params=params,
            timeout=30,
        )
        if response.status_code != 200:
            result.add_issue(f"NHD query failed with status code {response.status_code}.")
            return result

        data = response.json()
        if data.get("error"):
            result.add_issue(f"NHD query error: {data['error'].get('message', 'Unknown error')}.")
            return result

        features = data.get("features", [])
        streams = []
        for feature in features:
            attrs = feature.get("attributes", {})
            fcode = attrs.get("fcode")
            name = (attrs.get("gnis_name") or "").strip() or "Unnamed"
            length_km = attrs.get("lengthkm") or 0
            length_mi = round(length_km * 0.621371, 2)
            streams.append({
                "name": name,
                "type": fcode_labels.get(fcode, f"FCode {fcode}"),
                "length_mi": length_mi,
            })

        streams.sort(key=lambda s: s["name"])
        result.fields['streams'] = BAField(value=streams, source=FieldSource.AUTO, tag='streams')

    except Exception as e:
        result.add_issue(f"Error querying NHD: {str(e)}")

    return result


def query_ssurgo(geojson_polygon):
    """Query USDA Soil Data Access for map units intersecting the project footprint."""
    result = StepResult()
    try:
        import json
        geom_dict = json.loads(geojson_polygon) if isinstance(geojson_polygon, str) else geojson_polygon
        poly = shape(geom_dict)
        wkt = poly.wkt

        sql = f"""
            SELECT
                mu.muname,
                c.hydricrating,
                c.drainagecl,
                mu.farmlndcl
            FROM
                mapunit mu
                INNER JOIN component c ON c.mukey = mu.mukey AND c.majcompflag = 'Yes'
            WHERE
                mu.mukey IN (
                    SELECT * FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('{wkt}')
                )
            ORDER BY mu.muname
        """

        for attempt in range(2):
            try:
                response = requests.post(
                    "https://sdmdataaccess.sc.egov.usda.gov/tabular/post.rest",
                    data={"query": sql, "FORMAT": "JSON"},
                    timeout=60,
                )
                break
            except requests.exceptions.Timeout:
                if attempt == 1:
                    result.add_issue("SSURGO query timed out after two attempts. The SDA service may be temporarily unavailable.")
                    return result

        if response.status_code != 200:
            result.add_issue(f"SSURGO query failed with status code {response.status_code}.")
            return result

        data = response.json()
        rows = data.get("Table", [])

        soils = []
        seen = set()
        for row in rows:
            muname, hydric, drainage, farmland = row
            if muname in seen:
                continue
            seen.add(muname)
            soils.append({
                "map_unit_name": muname or "Unknown",
                "hydric_rating": hydric or "Not rated",
                "drainage_class": drainage or "Not rated",
                "farmland_class": farmland or "Not rated",
            })

        result.fields['soils'] = BAField(value=soils, source=FieldSource.AUTO, tag='soils')

    except Exception as e:
        result.add_issue(f"Error querying SSURGO: {str(e)}")

    return result
