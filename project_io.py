# Project I/O Operations
#── bafield_to_dict()        # BAField → plain dict
#── stepresult_to_dict()     # StepResult → plain dict
#── dict_to_bafield()        # plain dict → BAField
#── dict_to_stepresult()     # plain dict → StepResult
#── save_project()           # calls serializers, writes file
#── load_project()           # reads file, calls deserializers



from models import BAField, StepResult, FieldSource
import json

def bafield_to_dict(bafield):
    """Convert a BAField object to a plain dictionary."""

    return {
        'tag': bafield.tag,
        'value': bafield.value,
        'source': bafield.source.value,  # Store the enum member's value (string)
        'issues': bafield.issues
    }       

def stepresult_to_dict(stepresult):
    """Convert a StepResult object to a plain dictionary."""

    return {
        'fields': {tag: bafield_to_dict(field) for tag, field in stepresult.fields.items()},
        'issues': stepresult.issues,
        'status': stepresult.status
    } 

def dict_to_bafield(d):
    """Convert a plain dictionary to a BAField object."""

    return BAField(
        tag=d['tag'],
        value=d['value'],
        source=FieldSource(d['source']),  # Convert string back to FieldSource enum
        issues=d.get('issues', [])  # Use an empty list if 'issues' is not present
    )

def dict_to_stepresult(d):
    """Convert a plain dictionary to a StepResult object."""

    return StepResult(
        fields={tag: dict_to_bafield(field_dict) for tag, field_dict in d.get('fields', {}).items()},
        issues=d.get('issues', []),  # Use an empty list if 'issues' is not present
        status=d.get('status', 'success')  # Default to "success" if 'status' is not present
    )

def save_project(project, filename):
    """Save the project data to a file."""
    
    with open(filename, 'w') as f:
        json.dump(stepresult_to_dict(project), f, indent=4)

def load_project(filename):
    """Load the project data from a file."""

    with open(filename, 'r') as f:
        data = json.load(f)
        return dict_to_stepresult(data)