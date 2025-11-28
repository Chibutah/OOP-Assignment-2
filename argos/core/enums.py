"""
Enumerations and constants for the Argos platform.
"""

from enum import Enum, auto
from typing import Set


class EntityStatus(Enum):
    """Status of an entity in the system."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DELETED = "deleted"
    PENDING = "pending"


class PersonType(Enum):
    """Types of persons in the system."""
    STUDENT = "student"
    LECTURER = "lecturer"
    STAFF = "staff"
    ADMIN = "admin"
    GUEST = "guest"


class GradeLevel(Enum):
    """Academic grade levels."""
    FRESHMAN = "freshman"
    SOPHOMORE = "sophomore"
    JUNIOR = "junior"
    SENIOR = "senior"
    GRADUATE = "graduate"
    POSTGRADUATE = "postgraduate"


class EventType(Enum):
    """Types of events in the system."""
    ENROLLMENT = "enrollment"
    GRADING = "grading"
    FACILITY_ACCESS = "facility_access"
    SECURITY_INCIDENT = "security_incident"
    SYSTEM_ALERT = "system_alert"
    POLICY_CHANGE = "policy_change"
    ML_PREDICTION = "ml_prediction"


class PolicyType(Enum):
    """Types of policies in the system."""
    ENROLLMENT = "enrollment"
    ACCESS_CONTROL = "access_control"
    PRIVACY = "privacy"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    RESOURCE_ALLOCATION = "resource_allocation"


class MLModelType(Enum):
    """Types of machine learning models."""
    ENROLLMENT_PREDICTOR = "enrollment_predictor"
    ROOM_OPTIMIZER = "room_optimizer"
    ANOMALY_DETECTOR = "anomaly_detector"
    RECOMMENDATION_ENGINE = "recommendation_engine"


class ConstraintType(Enum):
    """Types of scheduling constraints."""
    HARD = "hard"  # Must be satisfied
    SOFT = "soft"  # Should be satisfied if possible


class AccessLevel(Enum):
    """Access levels for resources."""
    NONE = "none"
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    OWNER = "owner"


class ReportFormat(Enum):
    """Supported report formats."""
    JSON = "json"
    CSV = "csv"
    PDF = "pdf"
    XML = "xml"


class AuditAction(Enum):
    """Types of audit actions."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    POLICY_VIOLATION = "policy_violation"
