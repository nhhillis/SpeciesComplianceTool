# Maps IPaC common name substrings (lowercase) to template tag slugs.
# Used to match IPaC response species to sec2__<slug>__ipac checkbox tags.
# Add new species here when the template is updated.

IPAC_NAME_TO_TAG_SLUG = {
    "whooping crane":              "whooping_crane",
    "gray bat":                    "gray_bat",
    "indiana bat":                 "indiana_bat",
    "northern long-eared bat":     "nleb",
    "ozark big-eared bat":         "ozark_bigeared_bat",
    "peppered chub":               "peppered_chub",
    "neosho mucket":               "neosho_mucket",
    "ouachita rock pocketbook":    "ouachita_rpb",
    "scaleshell mussel":           "scaleshell_mussel",
    "winged mapleleaf":            "winged_mapleleaf",
    "benton county crayfish":      "benton_crayfish",
    "harperella":                  "harperella",
    "american burying beetle":     "abb",
    "eastern black rail":          "eastern_black_rail",
    "lesser prairie-chicken":      "lepc",
    "piping plover":               "piping_plover",
    "red knot":                    "red_knot",
    "red-cockaded woodpecker":     "rcwo",
    "arkansas river shiner":       "ark_river_shiner",
    "leopard darter":              "leopard_darter",
    "neosho madtom":               "neosho_madtom",
    "ozark cavefish":              "ozark_cavefish",
    "rabbitsfoot":                 "rabbitsfoot",
    "western fanshell":            "western_fanshell",
    "mead's milkweed":             "meads_milkweed",
    "missouri bladderpod":         "mo_bladderpod",
    "american alligator":          "am_alligator",
    "texas kangaroo rat":          "tx_kangaroo_rat",
    "tricolored bat":              "tricolored_bat",
    "alligator snapping turtle":   "alligator_snapping",
    "monarch butterfly":           "monarch",
    "western regal fritillary":    "western_regal_frit",
}

# Species whose critical habitat tags exist in the template
CRITHAB_TAG_SLUGS = {
    "whooping_crane",
    "peppered_chub",
    "ark_river_shiner",
    "leopard_darter",
    "neosho_mucket",
    "rabbitsfoot",
    "louisiana_pigtoe",
}


def resolve_tag_slug(common_name: str) -> str | None:
    """Return the tag slug for an IPaC common name, or None if not mapped."""
    lower = common_name.lower()
    for key, slug in IPAC_NAME_TO_TAG_SLUG.items():
        if key in lower:
            return slug
    return None
