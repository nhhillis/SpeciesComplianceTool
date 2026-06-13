import os
import sys
from models import ProjectMetadata
from ba_project import BiologicalAssessment


def main():
    if len(sys.argv) < 4:
        print("Usage: python main.py <kmz_path> <jp_number> <county>")
        sys.exit(1)

    kmz_path = sys.argv[1]
    jp_number = sys.argv[2]
    county = sys.argv[3]

    metadata = ProjectMetadata(jp_number=jp_number, county=county)
    ba = BiologicalAssessment(metadata)

    print(f"Running pipeline for JP {jp_number} — {county} County")
    ba.run_pipeline(kmz_path)

    issues = ba.get_issues()
    if issues:
        print("\nIssues encountered:")
        for issue in issues:
            print(f"  ! {issue}")

    if not ba.is_complete():
        print("\nPipeline did not complete successfully.")
        sys.exit(1)

    # Summary
    ipac = ba.results['ipac']
    kmz = ba.results['kmz_ingest']

    print(f"\n--- Results for JP {jp_number} ({county} County) ---")
    print(f"Acres:           {kmz.fields['acres'].value}")

    te_species = ipac.fields.get('te_species', None)
    print(f"TE Species:      {len(te_species.value) if te_species else 'N/A'} species")

    wetlands = ipac.fields.get('wetlands', None)
    print(f"Wetland records: {len(wetlands.value) if wetlands else 'N/A'}")

    migbirds = ipac.fields.get('migratory_birds', None)
    print(f"Migratory birds: {len(migbirds.value) if migbirds else 'N/A'} species")

    if te_species:
        print("\nTE Species list:")
        for s in te_species.value:
            ch = " [CRITICAL HABITAT]" if s['critical_habitat'] else ""
            print(f"  {s['common_name']} ({s['scientific_name']}) — {s['status']}{ch}")

    if wetlands and wetlands.value:
        print("\nWetlands:")
        for w in wetlands.value:
            area = w.get('wetland_area', 'N/A')
            name = w.get('wetland_name') or w.get('nwi_code', 'N/A')
            print(f"  {name}: {area} ac")

    if migbirds:
        print("\nMigratory Birds:")
        for b in migbirds.value:
            print(f"  {b['common_name']} — {b['level_of_concern']}")

    # Generate Project Data Summary
    output_dir = os.path.dirname(os.path.abspath(kmz_path))
    print(f"\nGenerating Project Data Summary...")
    out_result = ba.generate_outputs(output_dir)
    if out_result.status == "error":
        for issue in out_result.issues:
            print(f"  ! {issue}")
    else:
        print(f"  Saved: {out_result.fields['output_path'].value}")


if __name__ == "__main__":
    main()
