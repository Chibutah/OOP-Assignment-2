"""
Core entities for the Argos platform with rich inheritance hierarchy.
"""

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Union
from dataclasses import dataclass, field
from enum import Enum

from .enums import (
    EntityStatus, PersonType, GradeLevel, EventType, PolicyType, 
    MLModelType, ConstraintType, AccessLevel, AuditAction
)
from .interfaces import Reportable, Credential, AuthToken, MLModel, Constraint
from .exceptions import ValidationError, AuthorizationError


class AbstractEntity(ABC):
    """Base abstract entity with universal ID, lifecycle, and versioning."""
    
    def __init__(self, entity_id: Optional[str] = None):
        self._id = entity_id or str(uuid.uuid4())
        self._created_at = datetime.now(timezone.utc)
        self._updated_at = self._created_at
        self._version = 1
        self._status = EntityStatus.ACTIVE
        self._metadata: Dict[str, Any] = {}
    
    @property
    def id(self) -> str:
        """Get the entity ID."""
        return self._id
    
    @property
    def created_at(self) -> datetime:
        """Get creation timestamp."""
        return self._created_at
    
    @property
    def updated_at(self) -> datetime:
        """Get last update timestamp."""
        return self._updated_at
    
    @property
    def version(self) -> int:
        """Get current version."""
        return self._version
    
    @property
    def status(self) -> EntityStatus:
        """Get entity status."""
        return self._status
    
    def update(self, **kwargs) -> None:
        """Update entity with new data."""
        for key, value in kwargs.items():
            if hasattr(self, f"_{key}"):
                setattr(self, f"_{key}", value)
        self._updated_at = datetime.now(timezone.utc)
        self._version += 1
    
    def activate(self) -> None:
        """Activate the entity."""
        self._status = EntityStatus.ACTIVE
        self.update()
    
    def deactivate(self) -> None:
        """Deactivate the entity."""
        self._status = EntityStatus.INACTIVE
        self.update()
    
    def suspend(self) -> None:
        """Suspend the entity."""
        self._status = EntityStatus.SUSPENDED
        self.update()
    
    def delete(self) -> None:
        """Mark entity as deleted."""
        self._status = EntityStatus.DELETED
        self.update()
    
    def get_metadata(self, key: str) -> Any:
        """Get metadata value."""
        return self._metadata.get(key)
    
    def set_metadata(self, key: str, value: Any) -> None:
        """Set metadata value."""
        self._metadata[key] = value
        self.update()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entity to dictionary."""
        return {
            'id': self._id,
            'created_at': self._created_at.isoformat(),
            'updated_at': self._updated_at.isoformat(),
            'version': self._version,
            'status': self._status.value if hasattr(self._status, 'value') else str(self._status),
            'metadata': self._metadata
        }
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}(id={self._id})"
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self._id}, status={self._status.value})"


class Person(AbstractEntity):
    """Abstract base class for all persons in the system."""
    
    def __init__(self, first_name: str, last_name: str, email: str, person_type: PersonType, **kwargs):
        super().__init__(**kwargs)
        self._first_name = first_name
        self._last_name = last_name
        self._email = email
        self._person_type = person_type
        self._roles: Set[str] = set()
        self._credentials: List[Credential] = []
        self._active_tokens: List[AuthToken] = []
    
    @property
    def first_name(self) -> str:
        return self._first_name
    
    @property
    def last_name(self) -> str:
        return self._last_name
    
    @property
    def full_name(self) -> str:
        return f"{self._first_name} {self._last_name}"
    
    @property
    def email(self) -> str:
        return self._email
    
    @property
    def person_type(self) -> PersonType:
        return self._person_type
    
    @property
    def roles(self) -> Set[str]:
        return self._roles.copy()
    
    def add_role(self, role: str) -> None:
        """Add a role to the person."""
        self._roles.add(role)
        self.update()
    
    def remove_role(self, role: str) -> None:
        """Remove a role from the person."""
        self._roles.discard(role)
        self.update()
    
    def has_role(self, role: str) -> bool:
        """Check if person has a specific role."""
        return role in self._roles
    
    def add_credential(self, credential: Credential) -> None:
        """Add a credential to the person."""
        self._credentials.append(credential)
        self.update()
    
    def get_credentials(self) -> List[Credential]:
        """Get all credentials."""
        return self._credentials.copy()
    
    def add_token(self, token: AuthToken) -> None:
        """Add an active token."""
        self._active_tokens.append(token)
        self.update()
    
    def remove_token(self, token: AuthToken) -> None:
        """Remove a token."""
        self._active_tokens.remove(token)
        self.update()
    
    def get_active_tokens(self) -> List[AuthToken]:
        """Get all active tokens."""
        return [token for token in self._active_tokens if not token.is_expired()]


class Student(Person):
    """Student entity with academic-specific properties."""
    
    def __init__(self, first_name: str, last_name: str, email: str, student_id: str, 
                 grade_level: GradeLevel, **kwargs):
        super().__init__(first_name, last_name, email, PersonType.STUDENT, **kwargs)
        self._student_id = student_id
        self._grade_level = grade_level
        self._enrollments: Set[str] = set()  # Section IDs
        self._gpa: Optional[float] = None
        self._academic_standing: str = "good"
        self._advisor: Optional[str] = None  # Lecturer ID
    
    @property
    def student_id(self) -> str:
        return self._student_id
    
    @property
    def grade_level(self) -> GradeLevel:
        return self._grade_level
    
    @property
    def gpa(self) -> Optional[float]:
        return self._gpa
    
    @property
    def academic_standing(self) -> str:
        return self._academic_standing
    
    @property
    def advisor(self) -> Optional[str]:
        return self._advisor
    
    def enroll_in_section(self, section_id: str) -> None:
        """Enroll in a section."""
        self._enrollments.add(section_id)
        self.update()
    
    def drop_section(self, section_id: str) -> None:
        """Drop a section."""
        self._enrollments.discard(section_id)
        self.update()
    
    def get_enrollments(self) -> Set[str]:
        """Get all enrolled sections."""
        return self._enrollments.copy()

    @property
    def enrollments(self) -> Set[str]:
        """Backward-compatible property for enrollments used by API layers.

        Some parts of the codebase expect a `student.enrollments` attribute.
        Provide it as a read-only property that returns a copy of the internal set.
        """
        return self._enrollments.copy()
    
    def update_gpa(self, gpa: float) -> None:
        """Update GPA."""
        if not 0.0 <= gpa <= 4.0:
            raise ValidationError("GPA must be between 0.0 and 4.0")
        self._gpa = gpa
        self.update()
    
    def set_advisor(self, advisor_id: str) -> None:
        """Set academic advisor."""
        self._advisor = advisor_id
        self.update()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert student to dictionary."""
        base_dict = super().to_dict()
        base_dict.update({
            '_first_name': self._first_name,
            '_last_name': self._last_name,
            '_email': self._email,
            '_person_type': self._person_type.value,
            '_roles': list(self._roles),
            '_student_id': self._student_id,
            '_grade_level': self._grade_level.value,
            '_gpa': self._gpa,
            '_academic_standing': self._academic_standing,
            '_advisor': self._advisor,
            '_enrollments': list(self._enrollments)
        })
        return base_dict


class Lecturer(Person):
    """Lecturer entity with teaching-specific properties."""
    
    def __init__(self, first_name: str, last_name: str, email: str, employee_id: str, 
                 department: str, **kwargs):
        super().__init__(first_name, last_name, email, PersonType.LECTURER, **kwargs)
        self._employee_id = employee_id
        self._department = department
        self._courses: Set[str] = set()  # Course IDs
        self._office_hours: Dict[str, str] = {}
        self._research_interests: List[str] = []
        self._qualifications: List[str] = []
    
    @property
    def employee_id(self) -> str:
        return self._employee_id
    
    @property
    def department(self) -> str:
        return self._department
    
    @property
    def courses(self) -> Set[str]:
        return self._courses.copy()
    
    @property
    def office_hours(self) -> Dict[str, str]:
        return self._office_hours.copy()
    
    @property
    def research_interests(self) -> List[str]:
        return self._research_interests.copy()
    
    @property
    def qualifications(self) -> List[str]:
        return self._qualifications.copy()
    
    def add_course(self, course_id: str) -> None:
        """Add a course to teach."""
        self._courses.add(course_id)
        self.update()
    
    def remove_course(self, course_id: str) -> None:
        """Remove a course."""
        self._courses.discard(course_id)
        self.update()
    
    def set_office_hours(self, day: str, hours: str) -> None:
        """Set office hours for a day."""
        self._office_hours[day] = hours
        self.update()
    
    def add_research_interest(self, interest: str) -> None:
        """Add a research interest."""
        self._research_interests.append(interest)
        self.update()
    
    def add_qualification(self, qualification: str) -> None:
        """Add a qualification."""
        self._qualifications.append(qualification)
        self.update()


class Staff(Person):
    """Staff entity with administrative properties."""
    
    def __init__(self, first_name: str, last_name: str, email: str, employee_id: str, 
                 department: str, position: str, **kwargs):
        super().__init__(first_name, last_name, email, PersonType.STAFF, **kwargs)
        self._employee_id = employee_id
        self._department = department
        self._position = position
        self._permissions: Set[str] = set()
        self._managed_resources: Set[str] = set()
    
    @property
    def employee_id(self) -> str:
        return self._employee_id
    
    @property
    def department(self) -> str:
        return self._department
    
    @property
    def position(self) -> str:
        return self._position
    
    @property
    def permissions(self) -> Set[str]:
        return self._permissions.copy()
    
    @property
    def managed_resources(self) -> Set[str]:
        return self._managed_resources.copy()
    
    def add_permission(self, permission: str) -> None:
        """Add a permission."""
        self._permissions.add(permission)
        self.update()
    
    def remove_permission(self, permission: str) -> None:
        """Remove a permission."""
        self._permissions.discard(permission)
        self.update()
    
    def add_managed_resource(self, resource_id: str) -> None:
        """Add a managed resource."""
        self._managed_resources.add(resource_id)
        self.update()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert person to dictionary."""
        base_dict = super().to_dict()
        base_dict.update({
            '_first_name': self._first_name,
            '_last_name': self._last_name,
            '_email': self._email,
            '_person_type': self._person_type.value,
            '_roles': list(self._roles)
        })
        return base_dict


class Guest(Person):
    """Guest entity with limited access."""
    
    def __init__(self, first_name: str, last_name: str, email: str, 
                 sponsor_id: str, visit_purpose: str, **kwargs):
        super().__init__(first_name, last_name, email, PersonType.GUEST, **kwargs)
        self._sponsor_id = sponsor_id
        self._visit_purpose = visit_purpose
        self._expires_at: Optional[datetime] = None
        self._access_areas: Set[str] = set()
    
    @property
    def sponsor_id(self) -> str:
        return self._sponsor_id
    
    @property
    def visit_purpose(self) -> str:
        return self._visit_purpose
    
    @property
    def expires_at(self) -> Optional[datetime]:
        return self._expires_at
    
    @property
    def access_areas(self) -> Set[str]:
        return self._access_areas.copy()
    
    def set_expiration(self, expires_at: datetime) -> None:
        """Set guest expiration time."""
        self._expires_at = expires_at
        self.update()
    
    def add_access_area(self, area: str) -> None:
        """Add an access area."""
        self._access_areas.add(area)
        self.update()
    
    def is_expired(self) -> bool:
        """Check if guest access is expired."""
        if self._expires_at is None:
            return False
        return datetime.now(timezone.utc) > self._expires_at


class Course(AbstractEntity):
    """Course entity representing an academic course."""
    
    def __init__(self, course_code: str, title: str, description: str, 
                 credits: int, department: str, **kwargs):
        super().__init__(**kwargs)
        self._course_code = course_code
        self._title = title
        self._description = description
        self._credits = credits
        self._department = department
        self._prerequisites: Set[str] = set()  # Course IDs
        self._sections: Set[str] = set()  # Section IDs
        self._syllabus: Optional[str] = None  # Syllabus ID
    
    @property
    def course_code(self) -> str:
        return self._course_code
    
    @property
    def title(self) -> str:
        return self._title
    
    @property
    def description(self) -> str:
        return self._description
    
    @property
    def credits(self) -> int:
        return self._credits
    
    @property
    def department(self) -> str:
        return self._department
    
    @property
    def prerequisites(self) -> Set[str]:
        return self._prerequisites.copy()
    
    @property
    def sections(self) -> Set[str]:
        return self._sections.copy()
    
    @property
    def syllabus(self) -> Optional[str]:
        return self._syllabus
    
    def add_prerequisite(self, course_id: str) -> None:
        """Add a prerequisite course."""
        self._prerequisites.add(course_id)
        self.update()
    
    def add_section(self, section_id: str) -> None:
        """Add a section."""
        self._sections.add(section_id)
        self.update()
    
    def set_syllabus(self, syllabus_id: str) -> None:
        """Set the syllabus."""
        self._syllabus = syllabus_id
        self.update()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert course to dictionary."""
        base_dict = super().to_dict()
        base_dict.update({
            '_course_code': self._course_code,
            '_title': self._title,
            '_description': self._description,
            '_credits': self._credits,
            '_department': self._department,
            '_prerequisites': list(self._prerequisites),
            '_sections': list(self._sections),
            '_syllabus': self._syllabus
        })
        return base_dict


class Section(AbstractEntity):
    """Section entity representing a specific instance of a course."""
    
    def __init__(self, course_id: str, section_number: str, semester: str, 
                 year: int, instructor_id: str, **kwargs):
        super().__init__(**kwargs)
        self._course_id = course_id
        self._section_number = section_number
        self._semester = semester
        self._year = year
        self._instructor_id = instructor_id
        self._room_id: Optional[str] = None
        self._schedule: Dict[str, str] = {}  # day -> time
        self._capacity: int = 0
        self._enrolled: Set[str] = set()  # Student IDs
        self._waitlist: List[str] = []  # Student IDs in order
        self._enrollment_policy: Optional[str] = None
    
    @property
    def course_id(self) -> str:
        return self._course_id
    
    @property
    def section_number(self) -> str:
        return self._section_number
    
    @property
    def semester(self) -> str:
        return self._semester
    
    @property
    def year(self) -> int:
        return self._year
    
    @property
    def instructor_id(self) -> str:
        return self._instructor_id
    
    @property
    def room_id(self) -> Optional[str]:
        return self._room_id
    
    @property
    def schedule(self) -> Dict[str, str]:
        return self._schedule.copy()
    
    @property
    def capacity(self) -> int:
        return self._capacity
    
    @property
    def enrolled_count(self) -> int:
        return len(self._enrolled)
    
    @property
    def waitlist_count(self) -> int:
        return len(self._waitlist)
    
    @property
    def is_full(self) -> bool:
        return len(self._enrolled) >= self._capacity
    
    def set_room(self, room_id: str) -> None:
        """Set the room for this section."""
        self._room_id = room_id
        self.update()
    
    def set_schedule(self, day: str, time: str) -> None:
        """Set schedule for a day."""
        self._schedule[day] = time
        self.update()
    
    def set_capacity(self, capacity: int) -> None:
        """Set section capacity."""
        if capacity < 0:
            raise ValidationError("Capacity cannot be negative")
        self._capacity = capacity
        self.update()
    
    def enroll_student(self, student_id: str) -> bool:
        """Enroll a student. Returns True if enrolled, False if waitlisted."""
        if student_id in self._enrolled:
            return True  # Already enrolled
        
        if not self.is_full:
            self._enrolled.add(student_id)
            self.update()
            return True
        else:
            if student_id not in self._waitlist:
                self._waitlist.append(student_id)
                self.update()
            return False
    
    def drop_student(self, student_id: str) -> bool:
        """Drop a student. Returns True if dropped, False if not enrolled."""
        if student_id in self._enrolled:
            self._enrolled.remove(student_id)
            # Move first waitlisted student to enrolled
            if self._waitlist:
                next_student = self._waitlist.pop(0)
                self._enrolled.add(next_student)
            self.update()
            return True
        elif student_id in self._waitlist:
            self._waitlist.remove(student_id)
            self.update()
            return True
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert section to dictionary."""
        base_dict = super().to_dict()
        base_dict.update({
            '_course_id': self._course_id,
            '_section_number': self._section_number,
            '_semester': self._semester,
            '_year': self._year,
            '_instructor_id': self._instructor_id,
            '_room_id': self._room_id,
            '_schedule': self._schedule,
            '_capacity': self._capacity,
            '_enrolled': list(self._enrolled),
            '_waitlist': self._waitlist,
            '_enrollment_policy': self._enrollment_policy
        })
        return base_dict


class Grade(AbstractEntity):
    """Immutable grade entity."""
    
    def __init__(self, student_id: str, section_id: str, assessment_id: str,
                 grade_value: Union[str, float], letter_grade: str, 
                 percentage: float, **kwargs):
        super().__init__(**kwargs)
        self._student_id = student_id
        self._section_id = section_id
        self._assessment_id = assessment_id
        self._grade_value = grade_value
        self._letter_grade = letter_grade
        self._percentage = percentage
        self._graded_at = datetime.now(timezone.utc)
        self._grader_id: Optional[str] = None
        self._comments: str = ""
    
    @property
    def student_id(self) -> str:
        return self._student_id
    
    @property
    def section_id(self) -> str:
        return self._section_id
    
    @property
    def assessment_id(self) -> str:
        return self._assessment_id
    
    @property
    def grade_value(self) -> Union[str, float]:
        return self._grade_value
    
    @property
    def letter_grade(self) -> str:
        return self._letter_grade
    
    @property
    def percentage(self) -> float:
        return self._percentage
    
    @property
    def graded_at(self) -> datetime:
        return self._graded_at
    
    @property
    def grader_id(self) -> Optional[str]:
        return self._grader_id
    
    @property
    def comments(self) -> str:
        return self._comments
    
    def set_grader(self, grader_id: str) -> None:
        """Set the grader ID."""
        self._grader_id = grader_id
        self.update()
    
    def set_comments(self, comments: str) -> None:
        """Set grade comments."""
        self._comments = comments
        self.update()


class Facility(AbstractEntity):
    """Facility entity representing a building or area."""
    
    def __init__(self, name: str, facility_type: str, location: str, **kwargs):
        super().__init__(**kwargs)
        self._name = name
        self._facility_type = facility_type
        self._location = location
        self._rooms: Set[str] = set()  # Room IDs
        self._access_level: AccessLevel = AccessLevel.READ
        self._security_zones: Set[str] = set()
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def facility_type(self) -> str:
        return self._facility_type
    
    @property
    def location(self) -> str:
        return self._location
    
    @property
    def rooms(self) -> Set[str]:
        return self._rooms.copy()
    
    @property
    def access_level(self) -> AccessLevel:
        return self._access_level
    
    @property
    def security_zones(self) -> Set[str]:
        return self._security_zones.copy()
    
    def add_room(self, room_id: str) -> None:
        """Add a room to this facility."""
        self._rooms.add(room_id)
        self.update()
    
    def set_access_level(self, level: AccessLevel) -> None:
        """Set access level for this facility."""
        self._access_level = level
        self.update()
    
    def add_security_zone(self, zone: str) -> None:
        """Add a security zone."""
        self._security_zones.add(zone)
        self.update()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert facility to dictionary."""
        base_dict = super().to_dict()
        base_dict.update({
            '_name': self._name,
            '_facility_type': self._facility_type,
            '_location': self._location,
            '_rooms': list(self._rooms),
            '_access_level': self._access_level.value if hasattr(self._access_level, 'value') else str(self._access_level),
            '_security_zones': list(self._security_zones)
        })
        return base_dict


class Room(AbstractEntity):
    """Room entity representing a specific room in a facility."""
    
    def __init__(self, room_number: str, facility_id: str, room_type: str, 
                 capacity: int, **kwargs):
        super().__init__(**kwargs)
        self._room_number = room_number
        self._facility_id = facility_id
        self._room_type = room_type
        self._capacity = capacity
        self._equipment: Set[str] = set()
        self._access_control: bool = False
        self._booking_schedule: Dict[str, Any] = {}
    
    @property
    def room_number(self) -> str:
        return self._room_number
    
    @property
    def facility_id(self) -> str:
        return self._facility_id
    
    @property
    def room_type(self) -> str:
        return self._room_type
    
    @property
    def capacity(self) -> int:
        return self._capacity
    
    @property
    def equipment(self) -> Set[str]:
        return self._equipment.copy()
    
    @property
    def has_access_control(self) -> bool:
        return self._access_control
    
    def add_equipment(self, equipment: str) -> None:
        """Add equipment to the room."""
        self._equipment.add(equipment)
        self.update()
    
    def set_access_control(self, enabled: bool) -> None:
        """Enable/disable access control."""
        self._access_control = enabled
        self.update()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert room to dictionary."""
        base_dict = super().to_dict()
        base_dict.update({
            '_room_number': self._room_number,
            '_facility_id': self._facility_id,
            '_room_type': self._room_type,
            '_capacity': self._capacity,
            '_equipment': list(self._equipment),
            '_access_control': self._access_control,
            '_booking_schedule': self._booking_schedule
        })
        return base_dict
    
    def book_room(self, start_time: datetime, end_time: datetime, 
                  booker_id: str) -> bool:
        """Book the room for a time period."""
        # Simple booking logic - in practice, this would be more complex
        booking_key = f"{start_time.isoformat()}-{end_time.isoformat()}"
        if booking_key not in self._booking_schedule:
            self._booking_schedule[booking_key] = {
                'booker_id': booker_id,
                'start_time': start_time,
                'end_time': end_time
            }
            self.update()
            return True
        return False


class Event(AbstractEntity):
    """Event entity for event sourcing."""
    
    def __init__(self, event_type: EventType, stream_id: str, 
                 event_data: Dict[str, Any], **kwargs):
        super().__init__(**kwargs)
        self._event_type = event_type
        self._stream_id = stream_id
        self._event_data = event_data
        self._version = 1
        self._correlation_id: Optional[str] = None
        self._causation_id: Optional[str] = None
    
    @property
    def event_type(self) -> EventType:
        return self._event_type
    
    @property
    def stream_id(self) -> str:
        return self._stream_id
    
    @property
    def event_data(self) -> Dict[str, Any]:
        return self._event_data.copy()
    
    @property
    def correlation_id(self) -> Optional[str]:
        return self._correlation_id
    
    @property
    def causation_id(self) -> Optional[str]:
        return self._causation_id
    
    def set_correlation_id(self, correlation_id: str) -> None:
        """Set correlation ID for event tracking."""
        self._correlation_id = correlation_id
        self.update()
    
    def set_causation_id(self, causation_id: str) -> None:
        """Set causation ID for event tracking."""
        self._causation_id = causation_id
        self.update()


class Policy(AbstractEntity):
    """Policy entity for access control and business rules."""
    
    def __init__(self, name: str, policy_type: PolicyType, 
                 rules: Dict[str, Any], **kwargs):
        super().__init__(**kwargs)
        self._name = name
        self._policy_type = policy_type
        self._rules = rules
        self._priority: int = 0
        self._is_active: bool = True
        self._applies_to: Set[str] = set()  # Entity types or IDs
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def policy_type(self) -> PolicyType:
        return self._policy_type
    
    @property
    def rules(self) -> Dict[str, Any]:
        return self._rules.copy()
    
    @property
    def priority(self) -> int:
        return self._priority
    
    @property
    def is_active(self) -> bool:
        return self._is_active
    
    @property
    def applies_to(self) -> Set[str]:
        return self._applies_to.copy()
    
    def set_priority(self, priority: int) -> None:
        """Set policy priority."""
        self._priority = priority
        self.update()
    
    def activate(self) -> None:
        """Activate the policy."""
        self._is_active = True
        self.update()
    
    def deactivate(self) -> None:
        """Deactivate the policy."""
        self._is_active = False
        self.update()
    
    def add_applies_to(self, entity: str) -> None:
        """Add entity this policy applies to."""
        self._applies_to.add(entity)
        self.update()


class AuditLogEntry(AbstractEntity):
    """Immutable audit log entry."""
    
    def __init__(self, user_id: str, action: AuditAction, resource_type: str,
                 resource_id: str, details: Dict[str, Any], **kwargs):
        super().__init__(**kwargs)
        self._user_id = user_id
        self._action = action
        self._resource_type = resource_type
        self._resource_id = resource_id
        self._details = details
        self._ip_address: Optional[str] = None
        self._user_agent: Optional[str] = None
        self._timestamp = datetime.now(timezone.utc)
    
    @property
    def user_id(self) -> str:
        return self._user_id
    
    @property
    def action(self) -> AuditAction:
        return self._action
    
    @property
    def resource_type(self) -> str:
        return self._resource_type
    
    @property
    def resource_id(self) -> str:
        return self._resource_id
    
    @property
    def details(self) -> Dict[str, Any]:
        return self._details.copy()
    
    @property
    def ip_address(self) -> Optional[str]:
        return self._ip_address
    
    @property
    def user_agent(self) -> Optional[str]:
        return self._user_agent
    
    @property
    def timestamp(self) -> datetime:
        return self._timestamp
    
    def set_ip_address(self, ip_address: str) -> None:
        """Set IP address."""
        self._ip_address = ip_address
        self.update()
    
    def set_user_agent(self, user_agent: str) -> None:
        """Set user agent."""
        self._user_agent = user_agent
        self.update()
