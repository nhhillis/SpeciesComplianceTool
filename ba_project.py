
 
import pipeline_functions
from models import StepResult, BAField, FieldSource, ProjectMetadata


class BiologicalAssessment:
    def __init__(self, metadata):
        #takes a ProjectMetadata object, stores it, initialises an empty results dict.  
        self.metadata = metadata
        self.results = {}  # This will hold the results of each step in the pipeline

    def run_pipeline(self, kmz_path):
        #takes kmz_path, runs the pipeline functions in order, stores results in self.results dict.
        self.results['kmz_ingest'] = pipeline_functions.ingest_kmz(kmz_path)
        
        #if error in ingest_kmz, return results with error and stop pipeline
        if self.results["kmz_ingest"].status == "error":
            # stop pipeline, surface issues to user
            return 
          
    def query_ipac(geojson_polygon):
        #takes geojson_polygon, queries IPaC, returns results as a StepResult object.
        return pipeline_functions.query_ipac(geojson_polygon)