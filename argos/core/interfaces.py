"""
Core interfaces and abstract base classes for the Argos platform.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol, TypeVar, Generic
from datetime import datetime
from enum import Enum

from .enums import ReportFormat, AccessLevel, ConstraintType


T = TypeVar('T')
R = TypeVar('R')


class Reportable(ABC):
    """Interface for entities that can generate reports."""
    
    @abstractmethod
    def generate_report(self, format: ReportFormat, scope: Optional[Dict[str, Any]] = None) -> str:
        """Generate a report in the specified format."""
        pass


class PluginInterface(ABC):
    """Interface for pluggable modules."""
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin with configuration."""
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """Clean up plugin resources."""
        pass
    
    @abstractmethod
    def get_version(self) -> str:
        """Get plugin version."""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """Get list of plugin capabilities."""
        pass


class EnrollmentPolicy(ABC):
    """Abstract base class for enrollment policies."""
    
    @abstractmethod
    def can_enroll(self, student: 'Student', section: 'Section') -> bool:
        """Check if a student can enroll in a section."""
        pass
    
    @abstractmethod
    def get_priority(self, student: 'Student', section: 'Section') -> int:
        """Get enrollment priority for a student in a section."""
        pass
    
    @abstractmethod
    def get_policy_name(self) -> str:
        """Get the name of this policy."""
        pass


class Constraint(ABC):
    """Abstract base class for scheduling constraints."""
    
    @abstractmethod
    def is_satisfied(self, schedule: Dict[str, Any]) -> bool:
        """Check if the constraint is satisfied by the given schedule."""
        pass
    
    @abstractmethod
    def get_type(self) -> ConstraintType:
        """Get the type of this constraint."""
        pass
    
    @abstractmethod
    def get_weight(self) -> float:
        """Get the weight/importance of this constraint."""
        pass


class Credential(ABC):
    """Abstract base class for authentication credentials."""
    
    @abstractmethod
    def validate(self) -> bool:
        """Validate the credential."""
        pass
    
    @abstractmethod
    def is_expired(self) -> bool:
        """Check if the credential is expired."""
        pass
    
    @abstractmethod
    def get_credential_type(self) -> str:
        """Get the type of credential."""
        pass


class AuthToken(ABC):
    """Abstract base class for authentication tokens."""
    
    @abstractmethod
    def is_valid(self) -> bool:
        """Check if the token is valid."""
        pass
    
    @abstractmethod
    def is_expired(self) -> bool:
        """Check if the token is expired."""
        pass
    
    @abstractmethod
    def get_claims(self) -> Dict[str, Any]:
        """Get token claims."""
        pass
    
    @abstractmethod
    def refresh(self) -> 'AuthToken':
        """Refresh the token."""
        pass


class AccessControl(ABC):
    """Abstract base class for access control mechanisms."""
    
    @abstractmethod
    def check_access(self, user: 'Person', resource: str, action: str) -> bool:
        """Check if user has access to perform action on resource."""
        pass
    
    @abstractmethod
    def get_permissions(self, user: 'Person') -> List[str]:
        """Get list of permissions for user."""
        pass


class EventHandler(ABC):
    """Abstract base class for event handlers."""
    
    @abstractmethod
    def handle_event(self, event: 'Event') -> None:
        """Handle an event."""
        pass
    
    @abstractmethod
    def can_handle(self, event_type: str) -> bool:
        """Check if this handler can handle the event type."""
        pass


class MLModel(ABC):
    """Abstract base class for machine learning models."""
    
    @abstractmethod
    def train(self, data: List[Dict[str, Any]]) -> None:
        """Train the model with data."""
        pass
    
    @abstractmethod
    def predict(self, input_data: Dict[str, Any]) -> Any:
        """Make a prediction."""
        pass
    
    @abstractmethod
    def explain(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Explain a prediction."""
        pass
    
    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information."""
        pass
    
    @abstractmethod
    def save(self, path: str) -> None:
        """Save the model."""
        pass
    
    @abstractmethod
    def load(self, path: str) -> None:
        """Load the model."""
        pass


class Repository(ABC, Generic[T]):
    """Abstract base class for repositories."""
    
    @abstractmethod
    def save(self, entity: T) -> T:
        """Save an entity."""
        pass
    
    @abstractmethod
    def find_by_id(self, entity_id: str) -> Optional[T]:
        """Find entity by ID."""
        pass
    
    @abstractmethod
    def find_all(self, filters: Optional[Dict[str, Any]] = None) -> List[T]:
        """Find all entities matching filters."""
        pass
    
    @abstractmethod
    def delete(self, entity_id: str) -> bool:
        """Delete an entity by ID."""
        pass


class EventStore(ABC):
    """Abstract base class for event stores."""
    
    @abstractmethod
    def append_event(self, event: 'Event') -> None:
        """Append an event to the store."""
        pass
    
    @abstractmethod
    def get_events(self, stream_id: str, from_version: int = 0) -> List['Event']:
        """Get events for a stream."""
        pass
    
    @abstractmethod
    def get_snapshot(self, stream_id: str) -> Optional[Dict[str, Any]]:
        """Get the latest snapshot for a stream."""
        pass
    
    @abstractmethod
    def save_snapshot(self, stream_id: str, snapshot: Dict[str, Any]) -> None:
        """Save a snapshot for a stream."""
        pass


class PolicyEngine(ABC):
    """Abstract base class for policy engines."""
    
    @abstractmethod
    def evaluate_policy(self, policy: 'Policy', context: Dict[str, Any]) -> bool:
        """Evaluate a policy against context."""
        pass
    
    @abstractmethod
    def get_applicable_policies(self, context: Dict[str, Any]) -> List['Policy']:
        """Get policies applicable to context."""
        pass


class Scheduler(ABC):
    """Abstract base class for schedulers."""
    
    @abstractmethod
    def schedule(self, constraints: List[Constraint], resources: List[Any]) -> Dict[str, Any]:
        """Schedule resources subject to constraints."""
        pass
    
    @abstractmethod
    def optimize(self, schedule: Dict[str, Any], objective: str) -> Dict[str, Any]:
        """Optimize an existing schedule."""
        pass
