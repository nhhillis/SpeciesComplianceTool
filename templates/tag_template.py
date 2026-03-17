"""
tag_template.py

One-time utility to add meaningful w:tag attributes to every SDT
(content control) in the ODOT BA template docx.

Usage:
    python tag_template.py <input.docx> <output_tagged.docx>

Produces:
    - A tagged .docx (BA_template_tagged_v2026_01.docx)
    - A review report listing every SDT with tag and confidence

Tag naming convention:
    cover__<field>
    sec1__<field>
    sec2__<species>__<col>         ipac | watershed | waterbody | records
    sec2__crithab__<species>
    sec3_1__<field>
    sec3_2__<species>__<flag>
    sec3_4__str<n>__<field>        structure bat/bird assessment
    sec4__<species>__<col>         ESA determinations table
    sec4__generic<n>__<col>        generic placeholder rows in sec4 table
    sec5__<field>
    sec6__<field>
    NEEDS_REVIEW__sdt<n>
"""

import re, zipfile, os, sys

# ─────────────────────────────────────────────────────────────────────────────
# Row schemas: keyword_in_row_text → [ordered SDT tags for each SDT in row]
# ─────────────────────────────────────────────────────────────────────────────

# Section 2 species table  (IPaC | Watershed | Water Body | Records)
SEC2 = {
    "whooping crane":            ["sec2__whooping_crane__ipac",
                                  "sec2__whooping_crane__watershed",
                                  "sec2__whooping_crane__waterbody"],
    "gray bat":                  ["sec2__gray_bat__ipac",
                                  "sec2__gray_bat__watershed",
                                  "sec2__gray_bat__waterbody"],
    "indiana bat":               ["sec2__indiana_bat__ipac",
                                  "sec2__indiana_bat__watershed"],
    "northern long-eared bat":   ["sec2__nleb__ipac",
                                  "sec2__nleb__watershed"],
    "ozark big-eared bat":       ["sec2__ozark_bigeared_bat__ipac",
                                  "sec2__ozark_bigeared_bat__watershed"],
    "peppered chub":             ["sec2__peppered_chub__ipac",
                                  "sec2__peppered_chub__watershed",
                                  "sec2__peppered_chub__waterbody"],
    "neosho mucket":             ["sec2__neosho_mucket__ipac",
                                  "sec2__neosho_mucket__watershed",
                                  "sec2__neosho_mucket__waterbody",
                                  "sec2__neosho_mucket__records"],
    "ouachita rock pocketbook":  ["sec2__ouachita_rpb__ipac",
                                  "sec2__ouachita_rpb__watershed",
                                  "sec2__ouachita_rpb__waterbody",
                                  "sec2__ouachita_rpb__records"],
    "scaleshell":                ["sec2__scaleshell_mussel__ipac",
                                  "sec2__scaleshell_mussel__watershed",
                                  "sec2__scaleshell_mussel__waterbody",
                                  "sec2__scaleshell_mussel__records"],
    "winged mapleleaf":          ["sec2__winged_mapleleaf__ipac",
                                  "sec2__winged_mapleleaf__watershed",
                                  "sec2__winged_mapleleaf__waterbody",
                                  "sec2__winged_mapleleaf__records"],
    "benton county cave crayfish":["sec2__benton_crayfish__ipac",
                                  "sec2__benton_crayfish__watershed",
                                  "sec2__benton_crayfish__waterbody",
                                  "sec2__benton_crayfish__records"],
    "harperella":                ["sec2__harperella__ipac",
                                  "sec2__harperella__watershed"],
    "american burying beetle":   ["sec2__abb__ipac",
                                  "sec2__abb__watershed"],
    "eastern black rail":        ["sec2__eastern_black_rail__ipac",
                                  "sec2__eastern_black_rail__watershed"],
    "lesser prairie chicken":    ["sec2__lepc__ipac",
                                  "sec2__lepc__watershed"],
    "piping plover":             ["sec2__piping_plover__ipac",
                                  "sec2__piping_plover__watershed"],
    "red knot":                  ["sec2__red_knot__ipac",
                                  "sec2__red_knot__watershed"],
    "red-cockaded woodpecker":   ["sec2__rcwo__ipac",
                                  "sec2__rcwo__watershed"],
    "arkansas river shiner":     ["sec2__ark_river_shiner__ipac",
                                  "sec2__ark_river_shiner__watershed",
                                  "sec2__ark_river_shiner__waterbody",
                                  "sec2__ark_river_shiner__records"],
    "leopard darter":            ["sec2__leopard_darter__ipac",
                                  "sec2__leopard_darter__watershed",
                                  "sec2__leopard_darter__waterbody",
                                  "sec2__leopard_darter__records"],
    "neosho madtom":             ["sec2__neosho_madtom__ipac",
                                  "sec2__neosho_madtom__watershed",
                                  "sec2__neosho_madtom__waterbody",
                                  "sec2__neosho_madtom__records"],
    "ozark cavefish":            ["sec2__ozark_cavefish__ipac",
                                  "sec2__ozark_cavefish__watershed",
                                  "sec2__ozark_cavefish__waterbody"],
    "rabbitsfoot":               ["sec2__rabbitsfoot__ipac",
                                  "sec2__rabbitsfoot__watershed",
                                  "sec2__rabbitsfoot__waterbody",
                                  "sec2__rabbitsfoot__records"],
    "western fanshell":          ["sec2__western_fanshell__ipac",
                                  "sec2__western_fanshell__watershed",
                                  "sec2__western_fanshell__waterbody",
                                  "sec2__western_fanshell__records"],
    "mead":                      ["sec2__meads_milkweed__ipac",
                                  "sec2__meads_milkweed__watershed"],
    "missouri bladderpod":       ["sec2__mo_bladderpod__ipac",
                                  "sec2__mo_bladderpod__watershed"],
    "american alligator":        ["sec2__am_alligator__ipac",
                                  "sec2__am_alligator__watershed"],
    "texas kangaroo rat":        ["sec2__tx_kangaroo_rat__ipac",
                                  "sec2__tx_kangaroo_rat__watershed"],
    "tri-colored bat":           ["sec2__tricolored_bat__ipac",
                                  "sec2__tricolored_bat__watershed"],
    "alligator snapping turtle": ["sec2__alligator_snapping__ipac",
                                  "sec2__alligator_snapping__watershed"],
    "monarch butterfly":         ["sec2__monarch__ipac",
                                  "sec2__monarch__watershed"],
    "western regal fritillary":  ["sec2__western_regal_frit__ipac",
                                  "sec2__western_regal_frit__watershed"],
}

# Section 2 critical habitat (1 SDT per row)
SEC2_CH = {
    "whooping crane":        "sec2__crithab__whooping_crane",
    "peppered chub":         "sec2__crithab__peppered_chub",
    "arkansas river shiner": "sec2__crithab__ark_river_shiner",
    "leopard darter":        "sec2__crithab__leopard_darter",
    "neosho mucket":         "sec2__crithab__neosho_mucket",
    "rabbitsfoot":           "sec2__crithab__rabbitsfoot",
    "pigto":                 "sec2__crithab__louisiana_pigtoe",
}

def _sec4(slug, n_cols):
    """Generate Section 4 ESA determinations column tags for a species."""
    # Col order: habitat_present | activities_impact | no_effect |
    #            may_affect_dkey | nlaa | laa |
    #            not_likely_jeopardize | likely_jeopardize |
    #            field_studies | onhi_data | occupied_wb | crucial_hab
    all_cols = [
        f"sec4__{slug}__habitat_present",
        f"sec4__{slug}__activities_impact",
        f"sec4__{slug}__no_effect",
        f"sec4__{slug}__may_affect_dkey",
        f"sec4__{slug}__nlaa",
        f"sec4__{slug}__laa",
        f"sec4__{slug}__not_likely_jeopardize",
        f"sec4__{slug}__likely_jeopardize",
        f"sec4__{slug}__field_studies",
        f"sec4__{slug}__onhi_data",
        f"sec4__{slug}__occupied_wb",
        f"sec4__{slug}__crucial_hab",
    ]
    return all_cols[:n_cols]

def _sec4_generic(n, n_cols):
    return _sec4(f"generic{n}", n_cols)

# Section 4 ESA determinations table
# Generic placeholder rows (3 rows with "Click here to enter species...") = 10 cols each
# Named species rows at bottom of table
SEC4 = {
    # Generic placeholder rows (tool will populate these dynamically)
    "click here to enter species or critical habitat":
        None,  # handled specially — 3 rows, each 10 cols, numbered at runtime

    # Named species rows
    "american burying beetle":   _sec4("abb", 9),    # 9 cols (no occupied_wb col)
    "tricolored bat":            _sec4("tricolored_bat", 10),
    "alligator snapping turtle": _sec4("ast", 10),
    "monarch butterfly":         _sec4("monarch", 10),
    "western regal fritillary":  _sec4("wrf", 10),
}

# Section 3.4 structure inspection rows
# Two identical structure blocks (str1, str2). Row text is identical between them
# so we track which structure number we're on using a counter.
SEC3_4_ROWS = {
    "bridge type:":              ["__type_dropdown", "__multispan_chk", "__material_dropdown"],
    "culvert type:":             ["__type_dropdown", "__multispan_chk", "__material_dropdown"],
    "structure type:":           ["__type_dropdown", "__material_dropdown"],
    "method of inspection":      ["__inspect_visual", "__inspect_ladder",
                                  "__inspect_snooper", "__inspect_thermal",
                                  "__inspect_acoustic", "__inspect_emergence"],
    "bats observed":             ["__bats_observed", "__bat_signs"],
    "could not be fully inspected": ["__not_fully_inspected"],
}

# Section 5 bald eagle rows with 2 SDTs each (in footprint | within 660ft)
SEC5_TWO_COL = {
    "cottonwood, sycamore, pecan": ["sec5__eagle__large_trees_fp",
                                    "sec5__eagle__large_trees_660ft"],
    "open foraging areas":         ["sec5__eagle__open_foraging_fp",
                                    "sec5__eagle__open_foraging_660ft"],
    "potential bald eagle nests":  ["sec5__eagle__nests_fp",
                                    "sec5__eagle__nests_660ft"],
    "bald eagles observed":        ["sec5__eagle__observed_fp",
                                    "sec5__eagle__observed_660ft"],
}

# ─────────────────────────────────────────────────────────────────────────────
# Context rules for SDTs that don't sit in recognisable rows
# ─────────────────────────────────────────────────────────────────────────────
CONTEXT_RULES = [
    # Cover
    (r"USFWS Project Code\s*$",             "cover__usfws_project_code",         "high"),
    (r"IPaC official species list\s*$",     "cover__ipac_email",                 "high"),
    # Section 1
    (r"1\.2\. Project Description",         "sec1__project_type",                "high"),
    (r"Work\s+within\s+OHWM is expected",   "sec1__chk_work_in_ohwm",            "high"),
    (r"Project is OFF-SET alignment",       "sec1__chk_offset_alignment",        "high"),
    (r"or\s+NEW alignment",                 "sec1__chk_new_alignment",           "high"),
    (r"NO OFF EXISTING PAVEMENT",           "sec1__chk_no_offpavement",          "high"),
    (r"Project requires new ROW",           "sec1__chk_new_row",                 "high"),
    # Section 3.1
    (r"Soil Class\s*$",                     "sec3_1__soil_class",                "high"),
    (r"Soil Name\s*$",                      "sec3_1__soil_name",                 "high"),
    (r"Soil Type\s*$",                      "sec3_1__soil_type",                 "high"),
    (r"Soil Characteristics\s*$",           "sec3_1__soil_characteristics",      "high"),
    (r"Precipitation.*annual inches",       "sec3_1__precip_annual_inches",      "high"),
    (r"Growing Season.*days",               "sec3_1__growing_season_days",       "high"),
    (r"Mean Temperatures.*Summer",          "sec3_1__temp_summer",               "high"),
    (r"Winter min/max",                     "sec3_1__temp_winter",               "high"),
    (r"From Woods et al\. 2005",            "sec3_1__land_use_woods",            "high"),
    (r"From Field investigation",           "sec3_1__land_use_field",            "high"),
    # Section 3.2 survey
    (r"Pedestrian survey of entire",        "sec3_2__chk_pedestrian_survey",     "high"),
    (r"300-ft buffer.*karst",               "sec3_2__chk_karst_buffer",          "high"),
    (r"ONLY if project is within a karst",  "sec3_2__karst_reason",              "high"),
    # Whooping crane habitat
    (r"sandbars in large river channels",   "sec3_2__wc__sandbars",              "high"),
    (r"emergent wetlands.*Project Footprint","sec3_2__wc__emergent_acres",       "high"),
    (r"Croplands.*foraging.*95%",           "sec3_2__wc__croplands_95pct",       "high"),
    (r"Whooping Crane Corridor",            "sec3_2__wc__corridor_pct",          "high"),
    (r"Salt Plains National Wildlife",      "sec3_2__wc__salt_plains_15mi",      "high"),
    (r"Hackberry Flat or Foss",             "sec3_2__wc__hackberry_foss",        "high"),
    # Gray bat
    (r"Riparian forest near streams.*rivers.*0\.5",
                                            "sec3_2__gray_bat__riparian",        "high"),
    (r"Ozark Plateau National Wildlife",    "sec3_2__gray_bat__ozark_plateau",   "high"),
    (r"within 1 mile of a 10 mile cave",    "sec3_2__gray_bat__cave_10mi",       "high"),
    (r"within 1 mile of a 2 mile cave",     "sec3_2__gray_bat__cave_2mi",        "high"),
    (r"perennial and intermittent streams.*impacted",
                                            "sec3_2__gray_bat__stream_ft",       "high"),
    # Indiana bat
    (r"DBH of >= 5 inches occur",           "sec3_2__indiana_bat__trees_5in",    "high"),
    (r"10 trees or less with DBH of >= 5",  "sec3_2__indiana_bat__10trees",      "high"),
    (r"Riparian forest occurs within 1 mile","sec3_2__indiana_bat__riparian_1mi","high"),
    # NLEB / tree bat shared fields
    (r"DBH of >= 3 inches occur",           "sec3_2__nleb__trees_3in",           "high"),
    (r"10 trees or less with DBH of > = 3", "sec3_2__nleb__10trees",             "high"),
    (r"Barns or sheds occur within.*Footprint",
                                            "sec3_2__nleb__barns_sheds",         "high"),
    (r"Acres of trees within 100 feet",     "sec3_2__bat_tree__acres_0_100ft",   "high"),
    (r"Acres of trees between 100",         "sec3_2__bat_tree__acres_100_300ft", "high"),
    (r"Acres of trees greater than 300",    "sec3_2__bat_tree__acres_gt300ft",   "high"),
    # Ozark big-eared bat
    (r"Mature oak-hickory forest.*0\.5",    "sec3_2__ozark_bat__oak_hickory",    "high"),
    (r"Riparian forest near intermittent",  "sec3_2__ozark_bat__riparian_interm","high"),
    # ABB
    (r"native perennial plant vegetation.*shapefiles",
                                            "sec3_2__abb__native_veg_acres",     "high"),
    (r"Suitable habitat is present adjacent","sec3_2__abb__adjacent",            "high"),
    (r"McAlester Army Ammunition Plant",    "sec3_2__abb__conservation_lands",   "high"),
    # LEPC
    (r"sand bluestem.*sand sagebrush",      "sec3_2__lepc__grassland",           "high"),
    (r"Modeled habitat.*SGP CHAT 3",        "sec3_2__lepc__sgpchat3",            "high"),
    (r"Connectivity Zone.*SGP CHAT 2",      "sec3_2__lepc__sgpchat2",            "high"),
    (r"Focal Area.*SGP CHAT 1",             "sec3_2__lepc__sgpchat1",            "high"),
    (r"3 miles of an Active Lek Buffer",    "sec3_2__lepc__lek_3mi",             "high"),
    # Piping plover / red knot
    (r"sandy or gravelly shorelines.*0\.25","sec3_2__piping_plover__shoreline",  "high"),
    (r"Salt flats or mudflats.*reservoirs", "sec3_2__piping_plover__saltflats",  "high"),
    (r"Mudflats associated with reservoirs","sec3_2__red_knot__mudflats",        "high"),
    # RCWO
    (r"loblolly.*shortleaf.*longleaf pine", "sec3_2__rcwo__old_growth_pine",     "high"),
    (r"Park-like stands of pines",          "sec3_2__rcwo__park_pine",           "high"),
    (r"Living pine trees over 60",          "sec3_2__rcwo__pine_60yr",           "high"),
    (r"McCurtain County Wilderness",        "sec3_2__rcwo__mccurtain",           "high"),
    # Ozark cavefish
    (r"Clear groundwater-fed streams in caves",
                                            "sec3_2__ozark_cavefish__habitat",   "high"),
    # Alligator / AST
    (r"Fresh or brackish marshes.*ponds.*lakes",
                                            "sec3_2__am_alligator__habitat",     "high"),
    (r"Canopy covered.*stagnant.*deep",     "sec3_2__ast__deep_water",           "high"),
    (r"Submerged vegetation.*snags.*logs",  "sec3_2__ast__submerged",            "high"),
    (r"sandy soils.*656 ft",               "sec3_2__ast__forested_riparian",    "high"),
    (r"Little River.*Little River.*0\.25",  "sec3_2__ast__little_river",         "medium"),
    # Monarch / WRF
    (r"milkweed.*Asclepias.*Project",       "sec3_2__monarch__milkweed",         "high"),
    (r"flowering.*nectar.*monarch",         "sec3_2__monarch__nectar",           "high"),
    (r"additional native habitat.*Project", "sec3_2__monarch__native_habitat",   "high"),
    (r"violet.*Viola.*Project",             "sec3_2__monarch__violet",           "high"),
    (r"native grassland habitat",           "sec3_2__wrf__native_grassland",     "high"),
    (r"nectar.*regal fritillary",           "sec3_2__wrf__nectar",               "high"),
    # Section 3.4 bat present check
    (r"SEE GUIDANCE\s*$",                   "sec3_4__bat_present_chk",           "medium"),
    # Section 4
    (r"USFWS\s+Project Code\s*:",           "sec4__usfws_project_code",          "high"),
    (r"ODOT Project JP Number\s*:",         "sec4__odot_jp_number",              "high"),
    (r"ABB.*BO.*4\(d\) rule",              "sec4__chk_abb_dkey",                "high"),
    (r"Indiana bat or NLEB.*range-wide",    "sec4__chk_bat_dkey",                "high"),
    (r"FHWA Bat Programmatic",              "sec4__chk_bat_programmatic",        "high"),
    # Section 5 single-SDT rows
    (r"\bLake\b\s*$",                       "sec5__eagle__dist_lake",            "high"),
    (r"\bRiver\b\s*$",                      "sec5__eagle__dist_river",           "high"),
    (r"\bStream\b\s*$",                     "sec5__eagle__dist_stream",          "high"),
    (r"\bPond\b\s*$",                       "sec5__eagle__dist_pond",            "high"),
    # Section 6
    (r"no work on suitable.*drainage",      "sec6__chk_no_work_structures",      "high"),
    (r"Birds of Conservation Concern",      "sec6__bcc_nesting_habitat_type",    "high"),
    (r"Sparsely vegetated islands.*sandbars.*0\.25",
                                            "sec6__ilt__sandbars",               "high"),
    (r"habitat identified above.*provide overview",
                                            "sec6__ilt__habitat_narrative",      "high"),
]

COMPILED = [(re.compile(p, re.IGNORECASE | re.DOTALL), t, c)
            for p, t, c in CONTEXT_RULES]

# ─────────────────────────────────────────────────────────────────────────────
# Single-SDT row rules: match entire row text → single tag
# Used for rows that have 1 SDT and distinctive row-level text
# ─────────────────────────────────────────────────────────────────────────────
SINGLE_SDT_ROWS = [
    # ABB native veg acres (row has 1 SDT, contains "american burying beetle")
    (r"american burying beetle.*native perennial plant vegetation",
                                             "sec3_2__abb__native_veg_acres",    "high"),
    # Indiana bat rows
    (r"live or dead trees.*snags.*dbh.*>= 5 inches.*occur within",
                                             "sec3_2__indiana_bat__trees_5in",    "high"),
    (r"10 trees or less with dbh of >= 5",   "sec3_2__indiana_bat__10trees",      "high"),
    (r"riparian forest occurs within 1 mile","sec3_2__indiana_bat__riparian_1mi", "high"),
    # Note: Indiana bat corridors and forested acres rows have identical text to NLEB.
    # They are resolved by position (SDT 133=indiana corridors, 134=indiana acres,
    # 139=nleb corridors, 140=nleb acres) — handled via INDEX_TAGS below.
    # NLEB rows
    (r"live or dead trees.*snags.*dbh.*>= 3 inches.*occur within",
                                             "sec3_2__nleb__trees_3in",           "high"),
    (r"10 trees or less with dbh of > = 3",  "sec3_2__nleb__10trees",             "high"),
    (r"barns or sheds occur within.*footprint",
                                             "sec3_2__nleb__barns_sheds",         "high"),
    # Tricolored bat
    (r"live or dead trees.*snags.*dbh.*>= 4 inches.*occur within",
                                             "sec3_2__tcb__trees_4in",            "high"),
    # Ouachita rock pocketbook second checkbox
    (r"large mussel beds containing a diversity",
                                             "sec3_2__ouachita_rpb__mussel_beds", "high"),
    # Little River rows
    (r"little river.*little river national wildlife.*0\.25",
                                             "sec3_2__little_river_nwr",          "medium"),
    # Structure label rows
    (r"enter as bridge #1.*culvert #1.*structure #1",
                                             "sec3_4__str_label",                 "high"),
    # Section 6 no-work checkbox
    (r"based on existing plans.*no work on suitable.*drainage structures",
                                             "sec6__chk_no_work_structures",      "high"),
    # Section 3.2 survey flags
    (r"pedestrian survey of entire",         "sec3_2__chk_pedestrian_survey",     "high"),
    (r"survey includes 300-ft buffer.*karst","sec3_2__chk_karst_buffer",          "high"),
    (r"only if project is within a karst",   "sec3_2__karst_reason",              "high"),
]

COMPILED_SINGLE = [(re.compile(p, re.IGNORECASE | re.DOTALL), t, c)
                   for p, t, c in SINGLE_SDT_ROWS]

# ─────────────────────────────────────────────────────────────────────────────
# Index-based tags: SDTs whose context is ambiguous but position is known.
# Key = 1-based SDT index in the document.
# These are a last resort for SDTs that share row text with another SDT.
# ─────────────────────────────────────────────────────────────────────────────
INDEX_TAGS = {
    # ── Section 3.2 survey checkboxes ────────────────────────────────────────
    114: ("sec3_2__chk_pedestrian_survey",      "high"),
    115: ("sec3_2__chk_karst_buffer",           "high"),
    116: ("sec3_2__karst_reason",               "high"),
    # ── Section 3.2: first habitat checkbox per species ───────────────────────
    # These SDTs sit in rows whose text also contains the species name,
    # causing them to match SEC2 lookups. Index-based override wins.
    117: ("sec3_2__wc__sandbars",               "high"),  # Whooping Crane
    123: ("sec3_2__gray_bat__karst",            "high"),  # Gray Bat
    # Indiana bat, NLEB, TCB first checkboxes are handled by pattern correctly
    # but corridors/acres rows need index (identical text between species)
    133: ("sec3_2__indiana_bat__corridors",     "high"),
    134: ("sec3_2__indiana_bat__forested_acres","high"),
    139: ("sec3_2__nleb__corridors",            "high"),
    140: ("sec3_2__nleb__forested_acres",       "high"),
    # ── Section 3.2 species-prefixed rows ─────────────────────────────────────
    # Rows begin with species name so SEC2 match fires — override with index
    154: ("sec3_2__abb__native_veg_acres",      "high"),  # ABB acres (row starts "american burying beetle number...")
    170: ("sec3_2__leopard_darter__habitat",    "high"),
    171: ("sec3_2__neosho_madtom__habitat",     "high"),
    172: ("sec3_2__ozark_cavefish__habitat",    "high"),
    173: ("sec3_2__am_alligator__habitat",      "high"),
    174: ("sec3_2__am_alligator__little_river", "high"),
    175: ("sec3_2__rabbitsfoot__habitat",       "high"),
    176: ("sec3_2__tcb__karst",                 "high"),
    177: ("sec3_2__tcb__trees_4in",             "high"),
    178: ("sec3_2__tcb__barns_sheds",           "high"),
    179: ("sec3_2__tcb__corridors",             "high"),
    180: ("sec3_2__tcb__forested_acres",        "high"),
    184: ("sec3_2__ast__deep_water",            "high"),
    185: ("sec3_2__ast__submerged",             "high"),
    186: ("sec3_2__ast__forested_riparian",     "high"),
    187: ("sec3_2__ast__little_river",          "high"),
    188: ("sec3_2__monarch__milkweed",          "high"),
    189: ("sec3_2__monarch__nectar",            "high"),
    190: ("sec3_2__monarch__native_habitat",    "high"),
    191: ("sec3_2__wrf__violet",                "high"),
    192: ("sec3_2__wrf__native_grassland",      "high"),
    193: ("sec3_2__wrf__nectar",                "high"),
    # ── Section 3.4 structure rows ────────────────────────────────────────────
    195: ("sec3_4__str1__bat_present_chk",      "high"),
    196: ("sec3_4__str1__label",                "high"),
    214: ("sec3_4__str2__label",                "high"),
    # ── Section 4 table header checkboxes (layout artifacts) ─────────────────
    233: ("sec4__header__col1",                 "high"),
    234: ("sec4__header__col2",                 "high"),
    235: ("sec4__header__col3",                 "high"),
    236: ("sec4__header__col4",                 "high"),
    # ── Section 4 D-key checkboxes ────────────────────────────────────────────
    319: ("sec4__chk_bat_dkey",                 "high"),
    # ── Section 6 ─────────────────────────────────────────────────────────────
    333: ("sec6__chk_no_work_structures",       "high"),
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def plain(xml_frag):
    t = re.sub(r'<[^>]+>', ' ', xml_frag)
    # Decode common HTML entities before lowercasing
    t = t.replace('&gt;', '>').replace('&lt;', '<').replace('&amp;', '&')
    t = t.replace('&#x2019;', "'").replace('&apos;', "'").replace('&quot;', '"')
    return re.sub(r'\s+', ' ', t).strip().lower()


def context_match(text):
    for pat, tag, conf in COMPILED:
        if pat.search(text):
            return tag, conf
    return None, None


def inject_tag(sdt_xml, tag_value):
    """Return SDT XML with w:tag injected. No-op if tag already present."""
    if re.search(r'<w:tag\b', sdt_xml):
        return sdt_xml
    tag_elem = f'<w:tag w:val="{tag_value}"/>'
    inner = sdt_xml[len('<w:sdt>'):-len('</w:sdt>')]
    if '<w:sdtPr>' in inner:
        new_inner = inner.replace('<w:sdtPr>', f'<w:sdtPr>{tag_elem}', 1)
    else:
        new_inner = f'<w:sdtPr>{tag_elem}</w:sdtPr>' + inner
    return f'<w:sdt>{new_inner}</w:sdt>'


# ─────────────────────────────────────────────────────────────────────────────
# Main tagging logic
# ─────────────────────────────────────────────────────────────────────────────

def tag_template(input_path, output_path):
    with zipfile.ZipFile(input_path, 'r') as z:
        xml = z.read('word/document.xml').decode('utf-8')

    sdt_re = re.compile(r'<w:sdt>(.*?)</w:sdt>', re.DOTALL)
    tr_re  = re.compile(r'<w:tr\b[^>]*>(.*?)</w:tr>', re.DOTALL)

    all_sdts = list(sdt_re.finditer(xml))
    print(f"Found {len(all_sdts)} SDTs.")

    pos_to_tag = {}   # abs_position → (tag, confidence)
    sec4_generic_counter = 0
    sec3_4_str_counter   = 0   # tracks which structure block we're in

    for row_m in tr_re.finditer(xml):
        row_xml      = row_m.group(1)
        row_text     = plain(row_xml)
        inner_start  = row_m.start(1)
        row_sdts     = list(sdt_re.finditer(row_xml))
        if not row_sdts:
            continue

        def abs_pos(s): return inner_start + s.start()
        n_sdts = len(row_sdts)

        # ── Section 2 critical habitat (1 SDT per row) — check BEFORE species ─
        ch_tag = None
        for key, tag in SEC2_CH.items():
            if key in row_text:
                ch_tag = tag
                break
        if ch_tag and n_sdts == 1:
            pos_to_tag[abs_pos(row_sdts[0])] = (ch_tag, 'high')
            continue

        # ── Section 4 ESA determinations — generic rows ──────────────────────
        if "click here to enter species or critical habitat" in row_text:
            sec4_generic_counter += 1
            n = sec4_generic_counter
            cols = _sec4(f"generic{n}", min(n_sdts, 10))
            for j, s in enumerate(row_sdts):
                tag = cols[j] if j < len(cols) else f"sec4__generic{n}__col{j}"
                pos_to_tag[abs_pos(s)] = (tag, 'high')
            continue

        # ── Section 4 ESA determinations — named species rows (9-10 SDTs) ─────
        # Must check before SEC2 because some species names appear in both tables.
        # Discriminator: SEC4 rows have 9-10 SDTs; SEC2 rows have 2-4.
        if n_sdts >= 9:
            matched_sec4 = None
            for key, cols in SEC4.items():
                if key != "click here to enter species or critical habitat" \
                   and key in row_text and cols:
                    matched_sec4 = cols
                    break
            if matched_sec4:
                for j, s in enumerate(row_sdts):
                    tag = matched_sec4[j] if j < len(matched_sec4) \
                          else f"sec4__overflow_col{j}"
                    pos_to_tag[abs_pos(s)] = (tag, 'high')
                continue

        # ── Section 2 species table ──────────────────────────────────────────
        # Only match rows with 2-4 SDTs (species table never has more than 4)
        if n_sdts <= 4:
            matched_sec2 = None
            for key, cols in SEC2.items():
                if key in row_text:
                    matched_sec2 = cols
                    break
            if matched_sec2:
                for j, s in enumerate(row_sdts):
                    tag = matched_sec2[j] if j < len(matched_sec2) \
                          else f"sec2__overflow_col{j}"
                    pos_to_tag[abs_pos(s)] = (tag, 'high')
                continue

        # ── Section 3.4 structure inspection rows ────────────────────────────
        for key, suffixes in SEC3_4_ROWS.items():
            if key in row_text:
                # Detect structure number: increment when we see "bridge type:" again
                # and we've already seen a complete block
                if key == "bridge type:":
                    sec3_4_str_counter += 1
                n = sec3_4_str_counter if sec3_4_str_counter > 0 else 1
                prefix = f"sec3_4__str{n}"
                for j, s in enumerate(row_sdts):
                    suffix = suffixes[j] if j < len(suffixes) \
                             else f"__col{j}"
                    pos_to_tag[abs_pos(s)] = (f"{prefix}{suffix}", 'high')
                break

        # ── Section 5 bald eagle two-column rows ─────────────────────────────
        for key, cols in SEC5_TWO_COL.items():
            if key in row_text and len(row_sdts) == 2:
                for j, s in enumerate(row_sdts):
                    pos_to_tag[abs_pos(s)] = (cols[j], 'high')
                break

        # ── All other rows: context match on row text ─────────────────────────
        for s in row_sdts:
            if abs_pos(s) in pos_to_tag:
                continue
            # Try single-SDT row rules first (whole row as context)
            if len(row_sdts) == 1:
                for pat, tag, conf in COMPILED_SINGLE:
                    if pat.search(row_text):
                        pos_to_tag[abs_pos(s)] = (tag, conf)
                        break
            if abs_pos(s) in pos_to_tag:
                continue
            # Fall back to context match on text before this SDT in the row
            ctx = plain(row_xml[:s.start()]) + " " + row_text
            tag, conf = context_match(ctx)
            if tag:
                pos_to_tag[abs_pos(s)] = (tag, conf)

    # ── Pass 2: fallbacks for SDTs not tagged by row logic ───────────────────
    for idx, sdt_m in enumerate(all_sdts):
        pos     = sdt_m.start()
        inner   = sdt_m.group(1)
        sdt_num = idx + 1

        if pos in pos_to_tag:
            continue

        # Skip if already has a tag in the XML
        if re.search(r'<w:tag\b', inner):
            existing = re.search(r'<w:tag w:val="([^"]+)"', inner)
            pos_to_tag[pos] = (existing.group(1) if existing else 'EXISTING_UNNAMED',
                               'existing')
            continue

        # Index-based override for known positional SDTs
        if sdt_num in INDEX_TAGS:
            pos_to_tag[pos] = INDEX_TAGS[sdt_num]
            continue

        # Context match on 400 chars of plain text before this SDT
        ctx = plain(xml[max(0, pos - 400): pos])
        tag, conf = context_match(ctx)
        if tag:
            pos_to_tag[pos] = (tag, conf)

    # ── Pass 3: INDEX_TAGS always win — override anything set by row logic ────
    # Some rows have species names that cause SEC2 patterns to fire incorrectly
    # on Section 3.2 checkboxes. Force the correct tag by SDT index.
    for idx, sdt_m in enumerate(all_sdts):
        sdt_num = idx + 1
        if sdt_num in INDEX_TAGS:
            pos_to_tag[sdt_m.start()] = INDEX_TAGS[sdt_num]

    # ── Rebuild XML ────────────────────────────────────────────────────────────
    parts  = []
    cursor = 0
    report = []

    for idx, sdt_m in enumerate(all_sdts):
        pos      = sdt_m.start()
        sdt_xml  = sdt_m.group(0)
        inner    = sdt_m.group(1)
        content  = plain(inner)[:80]

        parts.append(xml[cursor:pos])

        existing_m = re.search(r'<w:tag w:val="([^"]+)"', inner)
        if existing_m:
            tag, conf = existing_m.group(1), 'existing'
            parts.append(sdt_xml)
        elif pos in pos_to_tag:
            tag, conf = pos_to_tag[pos]
            parts.append(inject_tag(sdt_xml, tag))
        else:
            tag  = f"NEEDS_REVIEW__sdt{idx+1}"
            conf = 'low'
            parts.append(inject_tag(sdt_xml, tag))

        report.append({'index': idx+1, 'tag': tag, 'confidence': conf,
                       'content': content})
        cursor = sdt_m.end()

    parts.append(xml[cursor:])
    new_xml = ''.join(parts)

    # ── Write docx ────────────────────────────────────────────────────────────
    tmp = output_path + '.tmp'
    with zipfile.ZipFile(input_path, 'r') as zin, \
         zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = new_xml.encode('utf-8') \
                   if item.filename == 'word/document.xml' \
                   else zin.read(item.filename)
            zout.writestr(item, data)
    os.replace(tmp, output_path)
    print(f"Tagged template → {output_path}")

    # ── Review report ─────────────────────────────────────────────────────────
    review_path = os.path.splitext(output_path)[0] + '_tag_review.txt'
    counts = {}
    for r in report:
        counts[r['confidence']] = counts.get(r['confidence'], 0) + 1
    needs = sum(1 for r in report if 'NEEDS_REVIEW' in r['tag'])

    with open(review_path, 'w', encoding='utf-8') as f:
        f.write("ODOT BA TEMPLATE — SDT TAG REVIEW REPORT\n")
        f.write("=" * 72 + "\n")
        f.write(f"Total SDTs:        {len(report)}\n")
        f.write(f"High confidence:   {counts.get('high', 0)}\n")
        f.write(f"Medium confidence: {counts.get('medium', 0)}\n")
        f.write(f"Existing tags:     {counts.get('existing', 0)}\n")
        f.write(f"Needs review:      {needs}  ← ACTION REQUIRED\n\n")
        f.write("Verify all MEDIUM and NEEDS_REVIEW entries.\n")
        f.write("-" * 72 + "\n\n")
        for r in report:
            flag = "  *** REVIEW ***" if 'NEEDS_REVIEW' in r['tag'] else \
                   "  * verify"       if r['confidence'] == 'medium' else ""
            f.write(f"SDT {r['index']:3d} | {r['confidence']:8s} | {r['tag']}{flag}\n")
            f.write(f"           content: {r['content']}\n\n")

    print(f"Review report  → {review_path}")
    print(f"\nSummary: {counts.get('high',0)} high | "
          f"{counts.get('medium',0)} medium | "
          f"{needs} need review | "
          f"{counts.get('existing',0)} existing")
    return report


def _sec4(slug, n_cols):
    all_cols = [
        f"sec4__{slug}__habitat_present",
        f"sec4__{slug}__activities_impact",
        f"sec4__{slug}__no_effect",
        f"sec4__{slug}__may_affect_dkey",
        f"sec4__{slug}__nlaa",
        f"sec4__{slug}__laa",
        f"sec4__{slug}__not_likely_jeopardize",
        f"sec4__{slug}__likely_jeopardize",
        f"sec4__{slug}__field_studies",
        f"sec4__{slug}__onhi_data",
        f"sec4__{slug}__occupied_wb",
        f"sec4__{slug}__crucial_hab",
    ]
    return all_cols[:n_cols]


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python tag_template.py <input.docx> <output_tagged.docx>")
        sys.exit(1)
    tag_template(sys.argv[1], sys.argv[2])
