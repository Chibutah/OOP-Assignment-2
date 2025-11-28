"""
Enrollment service with event sourcing and concurrency control.
"""

import asyncio
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from ..core.entities import Student, Section, Grade, Event, EventType
from ..core.interfaces import EnrollmentPolicy, EventHandler
from ..core.exceptions import EnrollmentError, ValidationError, ConcurrencyError
from .concurrency_manager import ConcurrencyManager, LockType


class EnrollmentStatus(Enum):
    """Status of an enrollment."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    WAITLISTED = "waitlisted"
    DROPPED = "dropped"
    REJECTED = "rejected"


@dataclass
class EnrollmentRequest:
    """Request to enroll a student in a section."""
    student_id: str
    section_id: str
    timestamp: float
    priority: int = 0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class EnrollmentResult:
    """Result of an enrollment operation."""
    success: bool
    status: EnrollmentStatus
    message: str
    waitlist_position: Optional[int] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class PrerequisiteCheckPolicy(EnrollmentPolicy):
    """Policy that checks prerequisites before enrollment."""
    
    def __init__(self, course_prerequisites: Dict[str, Set[str]]):
        self._course_prerequisites = course_prerequisites
    
    def can_enroll(self, student: Student, section: Section) -> bool:
        """Check if student meets prerequisites."""
        course_id = section.course_id
        if course_id not in self._course_prerequisites:
            return True  # No prerequisites defined
        
        required_courses = self._course_prerequisites[course_id]
        student_courses = set()  # Would be populated from student's completed courses
        
        return required_courses.issubset(student_courses)
    
    def get_priority(self, student: Student, section: Section) -> int:
        """Get enrollment priority."""
        return 0  # Default priority
    
    def get_policy_name(self) -> str:
        return "PrerequisiteCheckPolicy"


class QuotaPolicy(EnrollmentPolicy):
    """Policy that enforces enrollment quotas."""
    
    def __init__(self, max_enrollments: int = 30):
        self._max_enrollments = max_enrollments
    
    def can_enroll(self, student: Student, section: Section) -> bool:
        """Check if section has capacity."""
        return section.enrolled_count < self._max_enrollments
    
    def get_priority(self, student: Student, section: Section) -> int:
        """Get enrollment priority based on GPA."""
        if student.gpa is None:
            return 0
        return int(student.gpa * 100)  # Higher GPA = higher priority
    
    def get_policy_name(self) -> str:
        return "QuotaPolicy"


class PriorityPolicy(EnrollmentPolicy):
    """Policy that assigns priority based on student attributes."""
    
    def __init__(self, priority_rules: Dict[str, int]):
        self._priority_rules = priority_rules
    
    def can_enroll(self, student: Student, section: Section) -> bool:
        """All students can enroll if they meet basic requirements."""
        return True
    
    def get_priority(self, student: Student, section: Section) -> int:
        """Get priority based on student attributes."""
        priority = 0
        
        # Check student type
        if student.person_type.value in self._priority_rules:
            priority += self._priority_rules[student.person_type.value]
        
        # Check GPA
        if student.gpa is not None:
            if student.gpa >= 3.5:
                priority += 10
            elif student.gpa >= 3.0:
                priority += 5
        
        # Check grade level
        if student.grade_level.value in self._priority_rules:
            priority += self._priority_rules[student.grade_level.value]
        
        return priority
    
    def get_policy_name(self) -> str:
        return "PriorityPolicy"


class EnrollmentService:
    """Service for managing student enrollments with event sourcing."""
    
    def __init__(self, concurrency_manager: ConcurrencyManager):
        self._concurrency_manager = concurrency_manager
        self._enrollments: Dict[str, Dict[str, EnrollmentStatus]] = {}  # student_id -> section_id -> status
        self._waitlists: Dict[str, List[str]] = {}  # section_id -> [student_ids]
        self._policies: List[EnrollmentPolicy] = []
        self._event_handlers: List[EventHandler] = []
        self._lock = threading.RLock()
        
        # Initialize default policies
        self._add_default_policies()
    
    def _add_default_policies(self):
        """Add default enrollment policies."""
        # Prerequisite policy
        course_prerequisites = {
            "CS301": {"CS201", "CS202"},
            "CS401": {"CS301"},
            "MATH301": {"MATH201", "MATH202"}
        }
        self._policies.append(PrerequisiteCheckPolicy(course_prerequisites))
        
        # Quota policy
        self._policies.append(QuotaPolicy(max_enrollments=30))
        
        # Priority policy
        priority_rules = {
            "graduate": 20,
            "senior": 15,
            "junior": 10,
            "sophomore": 5,
            "freshman": 0
        }
        self._policies.append(PriorityPolicy(priority_rules))
    
    def add_policy(self, policy: EnrollmentPolicy) -> None:
        """Add an enrollment policy."""
        with self._lock:
            self._policies.append(policy)
    
    def remove_policy(self, policy_name: str) -> None:
        """Remove an enrollment policy by name."""
        with self._lock:
            self._policies = [p for p in self._policies if p.get_policy_name() != policy_name]
    
    def add_event_handler(self, handler: EventHandler) -> None:
        """Add an event handler."""
        with self._lock:
            self._event_handlers.append(handler)
    
    def enroll_student(self, student: Student, section: Section) -> EnrollmentResult:
        """Enroll a student in a section."""
        with self._lock:
            # Check if already enrolled
            if self._is_enrolled(student.id, section.id):
                return EnrollmentResult(
                    success=True,
                    status=EnrollmentStatus.CONFIRMED,
                    message="Student already enrolled"
                )
            
            # Apply enrollment policies
            can_enroll, policy_message = self._evaluate_policies(student, section)
            if not can_enroll:
                return EnrollmentResult(
                    success=False,
                    status=EnrollmentStatus.REJECTED,
                    message=policy_message
                )
            
            # Try to enroll
            try:
                with self._concurrency_manager.lock(
                    f"enrollment_{section.id}", 
                    LockType.WRITE, 
                    f"enrollment_service_{threading.get_ident()}"
                ):
                    if section.enrolled_count < section.capacity:
                        # Direct enrollment
                        self._enroll_student_direct(student.id, section.id)
                        self._publish_event(EventType.ENROLLMENT, {
                            'student_id': student.id,
                            'section_id': section.id,
                            'status': 'enrolled',
                            'timestamp': time.time()
                        })
                        
                        return EnrollmentResult(
                            success=True,
                            status=EnrollmentStatus.CONFIRMED,
                            message="Student enrolled successfully"
                        )
                    else:
                        # Add to waitlist
                        waitlist_position = self._add_to_waitlist(student.id, section.id)
                        self._publish_event(EventType.ENROLLMENT, {
                            'student_id': student.id,
                            'section_id': section.id,
                            'status': 'waitlisted',
                            'waitlist_position': waitlist_position,
                            'timestamp': time.time()
                        })
                        
                        return EnrollmentResult(
                            success=True,
                            status=EnrollmentStatus.WAITLISTED,
                            message=f"Student added to waitlist at position {waitlist_position}",
                            waitlist_position=waitlist_position
                        )
            
            except ConcurrencyError as e:
                return EnrollmentResult(
                    success=False,
                    status=EnrollmentStatus.REJECTED,
                    message=f"Concurrency error: {str(e)}"
                )
    
    def drop_student(self, student_id: str, section_id: str) -> EnrollmentResult:
        """Drop a student from a section."""
        with self._lock:
            if not self._is_enrolled(student_id, section_id):
                return EnrollmentResult(
                    success=False,
                    status=EnrollmentStatus.DROPPED,
                    message="Student not enrolled in this section"
                )
            
            try:
                with self._concurrency_manager.lock(
                    f"enrollment_{section_id}",
                    LockType.WRITE,
                    f"enrollment_service_{threading.get_ident()}"
                ):
                    # Remove from enrollments
                    if student_id in self._enrollments:
                        self._enrollments[student_id].pop(section_id, None)
                        if not self._enrollments[student_id]:
                            del self._enrollments[student_id]
                    
                    # Remove from waitlist if present
                    if section_id in self._waitlists and student_id in self._waitlists[section_id]:
                        self._waitlists[section_id].remove(student_id)
                    
                    # Move next student from waitlist to enrolled
                    if section_id in self._waitlists and self._waitlists[section_id]:
                        next_student_id = self._waitlists[section_id].pop(0)
                        self._enroll_student_direct(next_student_id, section_id)
                        
                        self._publish_event(EventType.ENROLLMENT, {
                            'student_id': next_student_id,
                            'section_id': section_id,
                            'status': 'enrolled_from_waitlist',
                            'timestamp': time.time()
                        })
                    
                    self._publish_event(EventType.ENROLLMENT, {
                        'student_id': student_id,
                        'section_id': section_id,
                        'status': 'dropped',
                        'timestamp': time.time()
                    })
                    
                    return EnrollmentResult(
                        success=True,
                        status=EnrollmentStatus.DROPPED,
                        message="Student dropped successfully"
                    )
            
            except ConcurrencyError as e:
                return EnrollmentResult(
                    success=False,
                    status=EnrollmentStatus.DROPPED,
                    message=f"Concurrency error: {str(e)}"
                )
    
    def _is_enrolled(self, student_id: str, section_id: str) -> bool:
        """Check if student is enrolled in section."""
        return (student_id in self._enrollments and 
                section_id in self._enrollments[student_id] and
                self._enrollments[student_id][section_id] == EnrollmentStatus.CONFIRMED)
    
    def _enroll_student_direct(self, student_id: str, section_id: str) -> None:
        """Directly enroll a student (internal method)."""
        if student_id not in self._enrollments:
            self._enrollments[student_id] = {}
        self._enrollments[student_id][section_id] = EnrollmentStatus.CONFIRMED
    
    def _add_to_waitlist(self, student_id: str, section_id: str) -> int:
        """Add student to waitlist and return position."""
        if section_id not in self._waitlists:
            self._waitlists[section_id] = []
        
        if student_id not in self._waitlists[section_id]:
            self._waitlists[section_id].append(student_id)
        
        return self._waitlists[section_id].index(student_id) + 1
    
    def _evaluate_policies(self, student: Student, section: Section) -> Tuple[bool, str]:
        """Evaluate all enrollment policies."""
        for policy in self._policies:
            if not policy.can_enroll(student, section):
                return False, f"Policy violation: {policy.get_policy_name()}"
        return True, "All policies satisfied"
    
    def _publish_event(self, event_type: EventType, event_data: Dict[str, Any]) -> None:
        """Publish an event to all handlers."""
        event = Event(
            event_type=event_type,
            stream_id=f"enrollment_{event_data.get('section_id', 'unknown')}",
            event_data=event_data
        )
        
        for handler in self._event_handlers:
            if handler.can_handle(event_type.value):
                try:
                    handler.handle_event(event)
                except Exception as e:
                    print(f"Error in event handler {handler.__class__.__name__}: {e}")
    
    def get_enrollments(self, student_id: str) -> List[str]:
        """Get all sections a student is enrolled in."""
        with self._lock:
            if student_id not in self._enrollments:
                return []
            return [section_id for section_id, status in self._enrollments[student_id].items()
                   if status == EnrollmentStatus.CONFIRMED]
    
    def get_waitlist_position(self, student_id: str, section_id: str) -> Optional[int]:
        """Get student's position on waitlist."""
        with self._lock:
            if section_id not in self._waitlists:
                return None
            if student_id not in self._waitlists[section_id]:
                return None
            return self._waitlists[section_id].index(student_id) + 1
    
    def get_section_enrollment_count(self, section_id: str) -> int:
        """Get number of students enrolled in a section."""
        with self._lock:
            count = 0
            for student_enrollments in self._enrollments.values():
                if section_id in student_enrollments and student_enrollments[section_id] == EnrollmentStatus.CONFIRMED:
                    count += 1
            return count
    
    def get_section_waitlist_count(self, section_id: str) -> int:
        """Get number of students on waitlist for a section."""
        with self._lock:
            return len(self._waitlists.get(section_id, []))
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get enrollment statistics."""
        with self._lock:
            total_enrollments = sum(len(enrollments) for enrollments in self._enrollments.values())
            total_waitlisted = sum(len(waitlist) for waitlist in self._waitlists.values())
            
            return {
                'total_enrollments': total_enrollments,
                'total_waitlisted': total_waitlisted,
                'active_policies': len(self._policies),
                'event_handlers': len(self._event_handlers)
            }
