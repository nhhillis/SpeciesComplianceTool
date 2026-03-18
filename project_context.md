# Project: NEPA Biological Assessment Automation Tool

## Purpose
Python tool to automate repetitive tasks in biological assessments for ODOT projects.
Reduces manual data gathering and drafting time for a team of ~50 environmental consultants.

## Core Stack
- Python + pdfplumber (PDF extraction)
- Streamlit (planned web UI)
- IPaC API (species data)
- Wetland/stream databases (TBD)

## Key Constraints
- Users are biologists, not developers — must be simple UI
- Team uses Bluebeam Revu (not Acrobat) for PDFs
- OCR is a rare edge case; handle with user instructions, not code
- YAGNI principle — core functionality first

## Architecture (Current)
- Module 1: PDF text extraction from Project Initiation Reports
  - Anchor: "Purpose & Need" section
  - Stop: After "Future ADT (20 Year Projection)"
  - Handles mixed content PDFs (text + image pages)
- Module 2: IPaC queries 
- Module 3: Wetland/stream data pulls (planned)
- Module 4: Draft BA section generation (planned)
- Module 5: Streamlit web interface (Month 3)

## Roadmap
- Month 1: Core data gathering (PDF extraction, IPaC, wetland/stream)
- Month 2: Draft document generation
- Month 3: Web interface + team presentation

## Architecture Insight: Generic Framework with Project-Specific Configuration
The core extraction engine is largely generic. The only project-specific elements are:

Document anchors (section headers to extract)
Metadata extraction (JP number, county — or equivalent fields for other project types)

This means the tool is better understood as a structured document automation framework configured for ODOT, not an ODOT-specific tool. Future document types (e.g. wetland delineation reports) would reuse the same engine with different configuration.
Design principle going forward: When facing flexibility vs. complexity tradeoffs, prioritize a working, demonstrable tool first. Build in flexibility only where it doesn't add meaningful complexity. The immediate goal is a polished demo that proves value to leadership.
Auto-detection was considered and deferred. Client document variety makes reliable anchor-based auto-detection impractical for now. A user-selected document type (one upfront choice) is the likely future path when multi-document support is needed.

## Template Tagging System
### Overview
The ODOT BA template (.docx) contains 336 Structured Document Tags (SDTs) — Word content controls that the tool populates programmatically. The tagging script (templates/tag_template.py) assigns meaningful w:tag attributes to all 336 SDTs so the document generation code can target them by name rather than by index.
#### Output files (in templates/):

BA_template_tagged_v2026_01.docx — the tagged template used for document generation
BA_template_tagged_v2026_01_tag_review.txt — full inventory of all 336 SDTs with tag names and confidence levels

#### Tag inventory summary:

319 high confidence tags (assigned by tag_template.py)
1 medium confidence tag — sec3_4__bat_present_chk (SDT 232) — verify placement before use
16 existing tags (present in original ODOT template, preserved as-is)
306 unique tag names total


##### Tagging Strategy
tag_template.py uses a three-pass strategy:

Row-based matching — identifies SDTs by their position within table rows
Context pattern matching — infers tag from surrounding text content
Index-based override — hardcoded assignments for SDTs that can't be resolved by context alone


#### Tag Naming Convention
Tags follow a section__entity__attribute pattern:
PrefixSectioncover__Cover page metadatasec1__Section 1 — project type checkboxessec2__Section 2 — species occurrence table (IPaC, watershed, waterbody, records, critical habitat)sec3_1__Section 3.1 — soils and climate datasec3_2__Section 3.2 — species-specific habitat assessment checkboxessec3_4__Section 3.4 — structure inspection (bat surveys, str1/str2)sec4__Section 4 — ESA effect determinations tablesec5__Section 5 — bald eagle assessmentsec6__Section 6 — interior least tern / migratory bird nesting
Section 2 suffix patterns:

__ipac — species flagged by IPaC query
__watershed — species present in watershed
__waterbody — species present in specific waterbody
__records — known occurrence records
__crithab__[species] — critical habitat present

#### Section 4 suffix patterns (per species row):

__habitat_present, __activities_impact, __no_effect, __may_affect_dkey, __nlaa, __laa, __not_likely_jeopardize, __likely_jeopardize, __field_studies, __onhi_data


#### Species Coverage
The template includes hardcoded rows for the following species (Section 4 has named rows; Section 2 covers all):
Bats: gray bat, Indiana bat, northern long-eared bat (NLEB), Ozark big-eared bat, tricolored bat
Aquatic species: peppered chub, Neosho mucket, Ouachita rock pocketbook, scaleshell mussel, winged mapleleaf, western fanshell, rabbitsfoot, Arkansas River shiner, leopard darter, Neosho madtom, Ozark cavefish, American alligator, alligator snapping turtle
Birds: whooping crane, American burying beetle (listed as invertebrate but treated here), eastern black rail, lesser prairie chicken (LEPC), piping plover, red knot, red-cockaded woodpecker (RCWO)
Plants/insects: Harperella, Mead's milkweed, Missouri bladderpod, monarch butterfly, western regal fritillary, Texas kangaroo rat
#### Section 4 also includes: 3 generic rows (generic1, generic2, generic3) for species not covered by named rows

#### Updating the Template
When ODOT revises the BA template or a new species must be added:

Update species_config.json with the new species entry
Add an INDEX_TAGS override entry in tag_template.py if context matching won't resolve it
Re-run tag_template.py to regenerate the tagged .docx and updated tag_review.txt
Increment the version string in the output filename (e.g. v2026_02)