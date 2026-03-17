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
