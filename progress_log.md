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
# Progress Log


2026-03-06
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
2026-03-02
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