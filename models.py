#Contains 
#FieldSource (enum with 3 members: AUTO, FIELD, and AUTHOR), 
#BAField (dataclass with four fields: value (any), source (FieldSource), tag (string), and issues (list of strings, default empty list)),
#StepResult (dataclass with 3 fields: fields (dict mapping sting names to BAField objects, default empty dict), 
#issues (list of strings, default empty list), and status (string, defauls to "success"))

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List  


# Define the FieldSource enum with three members: AUTO, FIELD, and AUTHOR
class FieldSource(Enum):
    AUTO = "Auto"
    FIELD = "Field"
    AUTHOR = "Author"

# Define the BAField dataclass with the specified fields
@dataclass
class BAField:
    value: Any
    source: FieldSource
    tag: str
    issues: List[str] = field(default_factory=list)

# Define the StepResult dataclass with the specified fields
@dataclass
class StepResult:
    fields: Dict[str, BAField] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    status: str = "success" 
    
    def add_issue(self, issue: str):
        self.issues.append(issue)
        self.status = "error"

#Define the ProjectMetadata dataclass with the specified fields
@dataclass
class ProjectMetadata:
    jp_number: str
    county: str
    preparer: str = ""
   
