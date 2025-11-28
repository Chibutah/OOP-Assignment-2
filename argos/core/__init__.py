"""
Core module containing the fundamental object model and base classes.
"""

from .entities import *
from .interfaces import *
from .exceptions import *
from .enums import *

__all__ = [
    # Entities
    "AbstractEntity",
    "Person",
    "Student",
    "Lecturer", 
    "Staff",
    "Guest",
    "Course",
    "Section",
    "Syllabus",
    "Assessment",
    "Grade",
    "Facility",
    "Room",
    "Resource",
    "Event",
    "EventStream",
    "AuditLogEntry",
    "Policy",
    "MLModel",
    
    # Interfaces
    "Reportable",
    "PluginInterface",
    "EnrollmentPolicy",
    "Constraint",
    "Credential",
    "AuthToken",
    
    # Enums
    "EntityStatus",
    "PersonType",
    "GradeLevel",
    "EventType",
    "PolicyType",
    "MLModelType",
    
    # Exceptions
    "ArgosException",
    "ValidationError",
    "AuthorizationError",
    "ConcurrencyError",
    "MLModelError",
]
