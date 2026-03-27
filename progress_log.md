## 2026-03-27
Completed

Added ProjectMetadata dataclass to models.py (jp_number, county, preparer)
Added add_issue() method to StepResult in models.py — sets status to "error" and appends issue message in one call
Created pipeline_functions.py with completed ingest_kmz(file_path) function

Checks for missing/empty KMZ file
Checks for zero or multiple KML files inside the KMZ
Parses KML coordinates into a Shapely polygon
Checks for invalid geometry
Reprojects to UTM Zone 14N and calculates acres
Returns StepResult with project_polygon, geojson_polygon, and acres as BAField objects (source: AUTO)



Decisions Made

County and JP number will be entered manually by the biologist at project setup — removed fragile filename parsing
ProjectMetadata holds project-setup fields (jp_number, county, preparer); dates are deferred to pipeline fields
ingest_kmz is a separate StepResult from query_ipac — better issue granularity for audit report
pipeline_functions.py is a new file; BiologicalAssessment.py will become the orchestrator

Current State of Code

models.py — complete (BAField, StepResult, FieldSource, ProjectMetadata)
project_io.py — complete (save/load, serialization round-trips)
pipeline_functions.py — ingest_kmz complete; query_ipac and extract_pdf not yet started
BiologicalAssessment.py — not yet refactored to orchestrator pattern

Next Session Goal

Implement query_ipac(polygon) in pipeline_functions.py
Include NWI REST API as IPaC wetland fallback within query_ipac

Open Questions

Ecoregion, soils, and watershed data sources not yet spiked — same five-step spike process needed before building
ProjectMetadata not yet wired into project_io.py serialization — needs metadata_to_dict / dict_to_metadata functions
FieldSource enum values are lowercase in JSON — confirm consistent with audit report rendering
## 2026-03-26

### Completed
- Built models.py — core data model for the tool
  - FieldSource enum (AUTO, FIELD, AUTHOR)
  - BAField dataclass (tag, value, source, issues)
  - StepResult dataclass (fields dict, issues list, status string)
- Built project_io.py — project file save/load system
  - bafield_to_dict() / dict_to_bafield() — BAField serialization round-trip
  - stepresult_to_dict() / dict_to_stepresult() — StepResult serialization round-trip
  - save_project() / load_project() — JSON file I/O

### Decisions Made
- Dedicated models.py for data model — keeps shape definitions separate from processing logic
- Dedicated project_io.py for file I/O — clean separation of responsibilities
- FieldSource enum values stored as lowercase strings in JSON (e.g. "auto") for human readability
- .get() with safe defaults used on all deserializer fields to handle missing keys gracefully
- import json and from models import BAField, StepResult, FieldSource at top of project_io.py

### Current State of Code
- models.py — complete
- project_io.py — complete
- Modules 1 and 2 (BiologicalAssessment.py) — complete, not yet refactored to use BAField

### Next Session Goal
- Stage 3: Refactor BiologicalAssessment.py so Modules 1 and 2 populate BAField objects
  instead of returning raw data

### Open Questions
- FieldSource enum values are lowercase — confirm this is consistent with how they'll
  appear in output documents and audit report  

## 2026-03-17
### Completed

Scoped v1 — confirmed core pipeline and trimmed scope to what is feasible and demonstrable
Designed two-output system: Project Data Summary (for biologist) and Data Audit Report (for QA/QC reviewer)
Designed step-level issue tracking model — each pipeline step stores data + a status/issues list; field-level tracking deferred to v2
Conducted NWI API spike — confirmed USFWS NWI MapServer REST service is viable as an IPaC wetland fallback for v1

Accepts envelope or polygon geometry input as JSON with spatialReference wkid 4326
Returns clean geoJSON with NWI attribute codes
Query pattern is similar to existing IPaC call — low effort to implement



### Decisions Made

NWI fallback added to v1 scope based on spike results
Issue tracking is step-level only for v1 — issues stored at pipeline step, rendered by section in output docs
Output documents are structured text, not templated .docx — keeps v1 complexity manageable
v1 UI is basic tkinter — shows populated fields, exports both output documents

### Current State of Code

Modules 1 and 2 complete
No new code written this session — design and scoping only

### Next Session Goal

Build BAField / FieldSource dataclasses
Design step result object with data + issues list
Begin wiring existing Module 1 and 2 outputs into new data model

### Open Questions

Ecoregion / soils / watershed data sources not yet spiked — same evaluation process needed before building

___________________________________________________________________________________________________________________

## Session — March 17, 2026

### What we covered

**Tool architecture and workflow design**
- Reviewed the uploaded ODOT BA guidance PDF and mapped the full report structure
- Designed a three-phase workflow: Pre-field (Phase 1), Post-field (Phase 2), Report authoring (Phase 3)
- Established the core design principle: tool is a data compiler and structure enforcer, not a decision-maker — the biologist retains all professional judgment
- Defined a BAField/FieldSource data model with three source types: AUTO (tool fetches), FIELD (biologist records), AUTHOR (biologist writes)
- Designed a two-output system: the BA report (.docx) for ODOT submittal and an audit report for reviewer verification
- Resolved key open questions: UI = tkinter, biologist authors directly in Word, ONHI = manual entry, GIS figures = data output only

**Field Maps schema design**
- Mapped field data collection to 5 Field Maps layers: Survey metadata, Community types, Structures, Special features, Photo points
- Confirmed bat habitat mapping and USFWS Appendix K forms are office tasks, not field capture
- Confirmed company has ArcGIS Online org account — enables a shared canonical Field Maps template
- Designed a per-project copy workflow: admin publishes master template, copies per project, shares with survey biologist

**ODOT template analysis and tagging**
- Analyzed the uploaded ODOT BA template (.docx): 336 SDTs (content controls), only 16 had existing tags
- Designed a versioned template management system with species_config.json as the stable API
- Built tag_template.py: a utility script that assigns meaningful w:tag attributes to all 336 SDTs
  - Uses three-pass strategy: row-based matching, context pattern matching, index-based override
  - Handles Section 2 species table, Section 2 critical habitat, Section 3.1-3.2, Section 3.4 structures, Section 4 ESA determinations, Sections 5-6
  - Final result: 319 high confidence + 1 medium + 16 existing = 336/336 tagged, 306 unique tags
- Generated BA_template_tagged_v2026_01.docx and tag_review.txt

**Repo housekeeping**
- Moved tag_template.py and review doc into templates/ folder
- Updated .gitignore to add outputs/ and project file patterns
- Added .gitattributes to handle line endings and mark .docx as binary
- Committed and pushed all changes

### Decisions made
- v1 scope confirmed: Phase 1 pipeline fully working + basic tkinter UI + partial .docx output
- Biologist-authored fields rendered as highlighted placeholders in Word draft
- SSURGO API identified as viable for auto-populating soils data in v1
- Ecoregion data: EPA shapefile (local) for spatial query; Woods et al. text = manual lookup for v1
- Template updates (e.g. new species) require: update species_config.json + add INDEX_TAGS entry + re-run tag_template.py

### Next steps
- Build BAField / FieldSource dataclasses (data model — Stage 1 of build sequence)
- Build project file save/load system (JSON — Stage 2)
- Refactor existing BiologicalAssessment.py to populate BAField objects (Stage 3)
- Design Field Maps attribute schema and hand to GIS admin

## 2026-03-09
### Completed
- Fixed startdate/enddate scoping bug in migratory bird breeding season block
- Added BCC level-of-concern dictionary to translate raw API strings to readable labels
- Handled unknown level-of-concern values with .get() fallback
- Module 2 now complete: species, migratory birds, and wetland state all parsing correctly

### Decisions Made
- Used dict.get() with fallback for level-of-concern translation
- BCC lookup dictionary keys: BCC_RANGEWIDE_CON, BCC_BCR_CON, NON_BCC_VULNERABLE, BCC_RANGEWIDE_PRV

### Current State of Code
- Module 1: Complete
- Module 2: Complete — IPaC query working, all three data types parsing cleanly

### Next Session Goal
- Begin Module 3: structured output object design for downstream document generation

### Open Questions
- Confirm exact API key string for BCC_RANGEWIDE_CON vs BCC_RANGEWIDE_CONCERN


## 2026-03-06
Completed this session:

Built IPaC API query using requests.post to /location/api/resources
Converted Shapely polygon to GeoJSON string using shapely.to_geojson()
Parsed species list from populationsBySid — common name, scientific name, listing status, critical habitat flag
Handled three wetland states: NWI unavailable (None), no wetlands found (empty list), wetlands present
Discovered allReferencedPopulationsBySid vs populationsBySid distinction — latter has project-specific flags like crithabInFootprint

Decisions made:

Use populationsBySid not allReferencedPopulationsBySid
Preserved full response as ipac_data to access wetlands/migbirds separately from species

Current state of code:

IPaC query working and tested against real project footprints
Wetland parsing not yet tested with live NWI data

Next session goals:

Test wetlands parsing when NWI data is available
Add migratory birds parsing
Begin thinking about structured output format for downstream document generation
---
## 2026-03-02
Completed

Built reusable extract_section(text, start_anchor, stop_anchor, skip_to) function
Added anchor-based extraction for Purpose & Need, Proposed Improvement, and Project Description
Handled label-line skipping using skip_to parameter (: for most sections, \n for Project Description)
Used .strip() to clean leading/trailing whitespace from results
Tested against real PIR (McClain JP 38881)

Decisions Made

Refactored three repeated extraction blocks into one reusable function (DRY principle)
skip_to defaults to ":" since most section labels end with a colon

Current State of Code

pdf_extractor.py — working, all three sections extracting cleanly

Next Session Goal

Begin Module 2 — IPaC queries

Open Questions

How consistent are section label formats across older PIR form versions?

## 2026-03-02
### Completed
- Built anchor-based PDF extractor using pdfplumber
- Handles mixed content (text + image pages) without crashing
- Extraction anchors on "Purpose & Need", stops at "Future ADT (20 Year Projection)"

### Decisions Made
- OCR not built in — user instructed to use Bluebeam Revu for image-based PDFs
- YAGNI applied — no multi-form version handling until needed

### Current State of Code
- `pdf_extractor.py` — working, tested on real PIRs
- `main.py` — basic CLI runner

### Next Session Goal
- Begin anchor-based extraction for "Proposed Improvement" and "Project Description" sections

### Open Questions
- How consistent is "Future ADT" label across older form versions?

---
## [previous date]
...