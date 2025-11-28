"""
Custom exceptions for the Argos platform.
"""

from typing import Optional, Any, Dict


class ArgosException(Exception):
    """Base exception for all Argos-related errors."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}


class ValidationError(ArgosException):
    """Raised when data validation fails."""
    pass


class AuthorizationError(ArgosException):
    """Raised when access is denied."""
    pass


class ConcurrencyError(ArgosException):
    """Raised when concurrency control fails."""
    pass


class MLModelError(ArgosException):
    """Raised when ML model operations fail."""
    pass


class PolicyViolationError(ArgosException):
    """Raised when a policy is violated."""
    pass


class ResourceNotFoundError(ArgosException):
    """Raised when a requested resource is not found."""
    pass


class DuplicateEntityError(ArgosException):
    """Raised when attempting to create a duplicate entity."""
    pass


class EnrollmentError(ArgosException):
    """Raised when enrollment operations fail."""
    pass


class SchedulingError(ArgosException):
    """Raised when scheduling operations fail."""
    pass


class SecurityError(ArgosException):
    """Raised when security operations fail."""
    pass


class PersistenceError(ArgosException):
    """Raised when persistence operations fail."""
    pass


class EventSourcingError(ArgosException):
    """Raised when event sourcing operations fail."""
    pass


class PluginError(ArgosException):
    """Raised when plugin operations fail."""
    pass


class ConfigurationError(ArgosException):
    """Raised when configuration is invalid."""
    pass


class NetworkError(ArgosException):
    """Raised when network operations fail."""
    pass


class TimeoutError(ArgosException):
    """Raised when operations timeout."""
    pass
