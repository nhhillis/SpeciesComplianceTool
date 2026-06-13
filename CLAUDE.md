# CLAUDE.md — Biological Assessment Automation Tool

## What This Project Is

A Python pipeline that automates data gathering and document scaffolding for NEPA
Biological Assessments (BAs) on ODOT (Oklahoma Department of Transportation) projects.
End users are biologists, not developers. The tool handles repetitive data collection;
the biologist retains all professional judgment and authorship of determinations.

## Tech Stack

- Python 3.x
- pdfplumber — PDF text extraction from Project Initiation Reports (PIRs)
- shapely, pyproj — geometry handling for project footprints
- python-docx — Word document generation
- requests — IPaC and NWI API calls
- tkinter — v1 UI (basic, functional)
- Streamlit — planned deployment target (Streamlit Community Cloud)

## Key Libraries Not to Substitute

- Do not swap pdfplumber for PyPDF2 or pypdf — pdfplumber handles mixed
  content (text + image pages) without crashing, which is a hard requirement.
- Do not use Acrobat-based approaches — team standard is Bluebeam Revu.
- OCR is intentionally excluded from code — edge cases handled by user instruction.

## Project File Structure

```
/
├── models.py              # BAField, FieldSource, StepResult dataclasses (Stage 1 — complete)
├── project_io.py          # save_project / load_project JSON serialization (Stage 2 — complete)
├── ba_project.py          # BiologicalAssessment orchestrator class (Stage 3 — in progress)
├── pipeline_functions.py  # ingest_kmz(), query_ipac(), etc. (Stage 3 — in progress)
├── BiologicalAssessment.py # Legacy — being cannibalized into pipeline_functions.py, then deleted
├── pdf_extractor.py       # PIR PDF extraction — complete
├── main.py                # CLI runner
└── templates/
    ├── BA_template_tagged_v2026_01.docx   # Tagged Word template (336 SDTs)
    ├── tag_template.py                    # Utility: assigns w:tag to all SDTs
    └── BA_template_tagged_v2026_01_tag_review.txt  # Full SDT inventory
```

## Data Model (models.py)

Three core classes — do not restructure without discussion:

**FieldSource** (enum): AUTO | FIELD | AUTHOR
- AUTO = tool fetched it from an API or file
- FIELD = biologist recorded it during field survey
- AUTHOR = biologist writes it as professional judgment

**BAField** (dataclass): tag, value, source (FieldSource), issues (List[str])
- One BAField per discrete piece of data
- tag matches the w:tag attribute in the Word template SDT

**StepResult** (dataclass): fields (Dict[str, BAField]), issues (List[str]), status (str)
- One StepResult per pipeline step
- All errors use result.add_issue() — never print statements
- Empty lists are valid data, not errors

## Pipeline Architecture

Single-button execution model. Steps run in sequence:

1. ingest_kmz() — reads KMZ, extracts project polygon and metadata
2. query_ipac() — POSTs polygon to IPaC Location API, parses species/wetlands/migbirds
3. query_nwi() — NWI REST MapServer fallback if IPaC wetlands unavailable
4. [future] query_ssurgo() — soils data
5. [future] extract_pir() — PDF extraction from PIR
6. [future] generate_outputs() — Project Data Summary + Data Audit Report (.docx)

## API Details

**IPaC Location API**
- Endpoint: https://ipac.ecosphere.fws.gov/location/api/resources
- Method: POST with GeoJSON polygon body
- Use populationsBySid (not allReferencedPopulationsBySid) — has project-specific flags
- Full response preserved as ipac_data before subsetting

**NWI REST MapServer**
- USFWS NWI MapServer REST service
- Accepts envelope or polygon geometry as JSON with spatialReference wkid 4326
- Returns GeoJSON with NWI attribute codes
- Used as fallback when IPaC wetlands data unavailable

## Word Template System

- 336 SDTs (Structured Document Tags / content controls) in the BA template
- All 336 tagged with meaningful w:tag attributes via tag_template.py
- 319 high confidence, 1 medium confidence (sec3_4__bat_present_chk — SDT 232, verify before use), 16 original
- 306 unique tag names
- Tag naming convention: section__entity__attribute (e.g. sec2__gray_bat__ipac)
- To update template: edit species_config.json → add INDEX_TAGS override if needed → re-run tag_template.py → increment version

## Output Documents (v1)

Two outputs, not one:
1. **Project Data Summary** — for the authoring biologist; shows all AUTO-populated fields
2. **Data Audit Report** — for QA/QC reviewer; shows data sources and any issues flagged

## Design Principles — Read Before Suggesting Changes

- **Working and demonstrable first.** v1 goal is a functional demo for leadership.
  Do not add complexity that doesn't serve that goal.
- **Single-button pipeline.** Minimize steps and failure points for biologist end-users.
- **Errors via add_issue(), never print().** Status propagates through StepResult.
- **Design before coding.** For any non-trivial feature, outline the approach before implementing.
- **YAGNI.** No multi-form version handling, no auto-detection of document type,
  no field-level issue tracking — all deferred to v2.
- **County and JP number are manually entered** at project setup — not parsed from filenames.
  Silent failure from filename parsing is worse than a simple input field.

## Domain Vocabulary

- **BA** — Biological Assessment (the report this tool helps produce)
- **ODOT** — Oklahoma Department of Transportation (the client)
- **PIR** — Project Initiation Report (source PDF with project description text)
- **IPaC** — USFWS Information for Planning and Consultation (species/wetland API)
- **NWI** — National Wetlands Inventory
- **SDT** — Structured Document Tag (Word content control, targeted by tag name)
- **ESA** — Endangered Species Act (Section 7 consultation is the compliance trigger)
- **JP number** — ODOT job/project number, manually entered at project setup
- **TE species** — Threatened and Endangered species flagged by IPaC query
- **BCC** — Birds of Conservation Concern (migratory bird level-of-concern categories)
- **NEPA** — National Environmental Policy Act (the regulatory framework)

## What NOT to Do

- Do not refactor models.py without explicit instruction — it is the stable foundation
  everything else builds on.
- Do not add a database — JSON project files are the intentional persistence layer for v1.
- Do not replace tkinter UI with anything — UI is intentionally minimal for v1.
- Do not add logging frameworks — issue tracking flows through StepResult.add_issue().
- Do not parse JP number or county from filenames — always prompt the user.
