import pipeline_functions
from models import StepResult, BAField, FieldSource, ProjectMetadata


class BiologicalAssessment:
    def __init__(self, metadata: ProjectMetadata):
        self.metadata = metadata
        self.results = {}

    def run_pipeline(self, kmz_path: str):
        # Step 1: KMZ ingest
        kmz_result = pipeline_functions.ingest_kmz(kmz_path)
        self.results['kmz_ingest'] = kmz_result
        if kmz_result.status == "error":
            return

        geojson_polygon = kmz_result.fields['geojson_polygon'].value

        # Step 2: IPaC query
        ipac_result = pipeline_functions.query_ipac(geojson_polygon)
        self.results['ipac'] = ipac_result

        # Step 3: NWI fallback if IPaC couldn't return wetland data
        if 'wetlands' not in ipac_result.fields:
            nwi_result = pipeline_functions.query_nwi(geojson_polygon)
            self.results['nwi'] = nwi_result
            # Promote NWI wetlands into the ipac result so downstream steps
            # always look in the same place
            if 'wetlands' in nwi_result.fields:
                ipac_result.fields['wetlands'] = nwi_result.fields['wetlands']

    def generate_outputs(self, output_dir: str):
        import os
        output_path = os.path.join(
            output_dir,
            f"JP{self.metadata.jp_number}_{self.metadata.county}_ProjectDataSummary.docx"
        )
        result = pipeline_functions.generate_project_data_summary(self, output_path)
        self.results['project_data_summary'] = result
        return result

    def get_issues(self) -> list[str]:
        """Collect all issues across every pipeline step."""
        issues = []
        for step_name, step_result in self.results.items():
            for issue in step_result.issues:
                issues.append(f"[{step_name}] {issue}")
        return issues

    def is_complete(self) -> bool:
        required = {'kmz_ingest', 'ipac'}
        return required.issubset(self.results) and all(
            self.results[k].status != "error" for k in required
        )
