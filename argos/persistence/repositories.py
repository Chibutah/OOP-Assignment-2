"""
Repository pattern implementations for data access.
"""

import json
import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, TypeVar, Generic
from datetime import datetime, timezone

from ..core.entities import (
    Student, Lecturer, Staff, Guest, Course, Section, Grade, 
    Facility, Room, AbstractEntity
)
from ..core.enums import EntityStatus
from ..core.interfaces import Repository
from ..core.exceptions import PersistenceError, ResourceNotFoundError
from .database import DatabaseManager

T = TypeVar('T', bound=AbstractEntity)


class BaseRepository(Repository[T], Generic[T]):
    """Base repository implementation with common functionality."""
    
    def __init__(self, database: DatabaseManager, entity_type: str):
        self._database = database
        self._entity_type = entity_type
        self._lock = threading.RLock()
    
    def save(self, entity: T) -> T:
        """Save an entity."""
        with self._lock:
            try:
                # Check if entity exists
                existing = self.find_by_id(entity.id)
                
                if existing:
                    # Update existing entity
                    query = """
                        UPDATE entities 
                        SET data = ?, updated_at = ?, version = ?, status = ?
                        WHERE id = ? AND type = ?
                    """
                    params = (
                        json.dumps(entity.to_dict()),
                        datetime.now(timezone.utc).isoformat(),
                        entity.version,
                        entity.status.value if hasattr(entity.status, 'value') else str(entity.status),
                        entity.id,
                        self._entity_type
                    )
                    self._database.execute_update(query, params)
                else:
                    # Insert new entity
                    query = """
                        INSERT INTO entities (id, type, data, created_at, updated_at, version, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """
                    params = (
                        entity.id,
                        self._entity_type,
                        json.dumps(entity.to_dict()),
                        entity.created_at.isoformat(),
                        entity.updated_at.isoformat(),
                        entity.version,
                        entity.status.value if hasattr(entity.status, 'value') else str(entity.status)
                    )
                    self._database.execute_update(query, params)
                
                return entity
            except Exception as e:
                raise PersistenceError(f"Failed to save {self._entity_type}: {str(e)}")
    
    def find_by_id(self, entity_id: str) -> Optional[T]:
        """Find entity by ID."""
        with self._lock:
            try:
                query = "SELECT data FROM entities WHERE id = ? AND type = ?"
                results = self._database.execute_query(query, (entity_id, self._entity_type))
                
                if results:
                    entity_data = json.loads(results[0]["data"])
                    return self._entity_from_dict(entity_data)
                return None
            except Exception as e:
                raise PersistenceError(f"Failed to find {self._entity_type} by ID: {str(e)}")
    
    def find_all(self, filters: Optional[Dict[str, Any]] = None) -> List[T]:
        """Find all entities matching filters."""
        with self._lock:
            try:
                query = "SELECT data FROM entities WHERE type = ?"
                params = [self._entity_type]
                
                if filters:
                    for key, value in filters.items():
                        if key == "status":
                            query += " AND status = ?"
                            params.append(value)
                        elif key == "created_after":
                            query += " AND created_at > ?"
                            params.append(value)
                        elif key == "created_before":
                            query += " AND created_at < ?"
                            params.append(value)
                
                query += " ORDER BY created_at DESC"
                
                results = self._database.execute_query(query, tuple(params))
                entities = []
                
                for row in results:
                    entity_data = json.loads(row["data"])
                    entity = self._entity_from_dict(entity_data)
                    entities.append(entity)
                
                return entities
            except Exception as e:
                raise PersistenceError(f"Failed to find {self._entity_type}s: {str(e)}")
    
    def delete(self, entity_id: str) -> bool:
        """Delete an entity by ID."""
        with self._lock:
            try:
                query = "DELETE FROM entities WHERE id = ? AND type = ?"
                affected_rows = self._database.execute_update(query, (entity_id, self._entity_type))
                return affected_rows > 0
            except Exception as e:
                raise PersistenceError(f"Failed to delete {self._entity_type}: {str(e)}")
    
    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count entities matching filters."""
        with self._lock:
            try:
                query = "SELECT COUNT(*) as count FROM entities WHERE type = ?"
                params = [self._entity_type]
                
                if filters:
                    for key, value in filters.items():
                        if key == "status":
                            query += " AND status = ?"
                            params.append(value)
                
                results = self._database.execute_query(query, tuple(params))
                return results[0]["count"] if results else 0
            except Exception as e:
                raise PersistenceError(f"Failed to count {self._entity_type}s: {str(e)}")
    
    @abstractmethod
    def _entity_from_dict(self, data: Dict[str, Any]) -> T:
        """Convert dictionary to entity instance."""
        pass


class StudentRepository(BaseRepository[Student]):
    """Repository for Student entities."""
    
    def __init__(self, database: DatabaseManager):
        super().__init__(database, "student")
    
    def _entity_from_dict(self, data: Dict[str, Any]) -> Student:
        """Convert dictionary to Student instance."""
        from ..core.enums import PersonType, GradeLevel
        
        student = Student(
            first_name=data["_first_name"],
            last_name=data["_last_name"],
            email=data["_email"],
            student_id=data["_student_id"],
            grade_level=GradeLevel(data["_grade_level"]),
            entity_id=data["id"]
        )
        
        # Restore additional properties
        student._gpa = data.get("_gpa")
        student._academic_standing = data.get("_academic_standing", "good")
        student._advisor = data.get("_advisor")
        student._enrollments = set(data.get("_enrollments", []))
        student._roles = set(data.get("_roles", []))
        student._created_at = datetime.fromisoformat(data["created_at"])
        student._updated_at = datetime.fromisoformat(data["updated_at"])
        student._version = data["version"]
        # Restore status enum (be defensive: handle str, enum, or missing)
        _status_raw = data.get("status")
        if isinstance(_status_raw, EntityStatus):
            student._status = _status_raw
        elif _status_raw is None:
            student._status = EntityStatus.ACTIVE
        else:
            try:
                student._status = EntityStatus(_status_raw)
            except Exception:
                try:
                    student._status = EntityStatus[_status_raw]
                except Exception:
                    student._status = EntityStatus.ACTIVE
        student._metadata = data.get("metadata", {})
        
        return student
    
    def find_by_student_id(self, student_id: str) -> Optional[Student]:
        """Find student by student ID."""
        students = self.find_all()
        for student in students:
            if student.student_id == student_id:
                return student
        return None
    
    def find_by_email(self, email: str) -> Optional[Student]:
        """Find student by email."""
        students = self.find_all()
        for student in students:
            if student.email == email:
                return student
        return None
    
    def find_by_grade_level(self, grade_level: str) -> List[Student]:
        """Find students by grade level."""
        students = self.find_all()
        return [s for s in students if s.grade_level.value == grade_level]
    
    def find_by_advisor(self, advisor_id: str) -> List[Student]:
        """Find students by advisor."""
        students = self.find_all()
        return [s for s in students if s.advisor == advisor_id]


class LecturerRepository(BaseRepository[Lecturer]):
    """Repository for Lecturer entities."""
    
    def __init__(self, database: DatabaseManager):
        super().__init__(database, "lecturer")
    
    def _entity_from_dict(self, data: Dict[str, Any]) -> Lecturer:
        """Convert dictionary to Lecturer instance."""
        from ..core.enums import PersonType
        
        lecturer = Lecturer(
            first_name=data["_first_name"],
            last_name=data["_last_name"],
            email=data["_email"],
            employee_id=data["_employee_id"],
            department=data["_department"],
            entity_id=data["id"]
        )
        
        # Restore additional properties
        lecturer._courses = set(data.get("_courses", []))
        lecturer._office_hours = data.get("_office_hours", {})
        lecturer._research_interests = data.get("_research_interests", [])
        lecturer._qualifications = data.get("_qualifications", [])
        lecturer._roles = set(data.get("_roles", []))
        lecturer._created_at = datetime.fromisoformat(data["created_at"])
        lecturer._updated_at = datetime.fromisoformat(data["updated_at"])
        lecturer._version = data["version"]
        _status_raw = data.get("status")
        if isinstance(_status_raw, EntityStatus):
            lecturer._status = _status_raw
        elif _status_raw is None:
            lecturer._status = EntityStatus.ACTIVE
        else:
            try:
                lecturer._status = EntityStatus(_status_raw)
            except Exception:
                try:
                    lecturer._status = EntityStatus[_status_raw]
                except Exception:
                    lecturer._status = EntityStatus.ACTIVE
        lecturer._metadata = data.get("metadata", {})
        
        return lecturer
    
    def find_by_employee_id(self, employee_id: str) -> Optional[Lecturer]:
        """Find lecturer by employee ID."""
        lecturers = self.find_all()
        for lecturer in lecturers:
            if lecturer.employee_id == employee_id:
                return lecturer
        return None
    
    def find_by_department(self, department: str) -> List[Lecturer]:
        """Find lecturers by department."""
        lecturers = self.find_all()
        return [l for l in lecturers if l.department == department]
    
    def find_by_course(self, course_id: str) -> List[Lecturer]:
        """Find lecturers teaching a specific course."""
        lecturers = self.find_all()
        return [l for l in lecturers if course_id in l.courses]


class CourseRepository(BaseRepository[Course]):
    """Repository for Course entities."""
    
    def __init__(self, database: DatabaseManager):
        super().__init__(database, "course")
    
    def _entity_from_dict(self, data: Dict[str, Any]) -> Course:
        """Convert dictionary to Course instance."""
        course = Course(
            course_code=data["_course_code"],
            title=data["_title"],
            description=data["_description"],
            credits=data["_credits"],
            department=data["_department"],
            entity_id=data["id"]
        )
        
        # Restore additional properties
        course._prerequisites = set(data.get("_prerequisites", []))
        course._sections = set(data.get("_sections", []))
        course._syllabus = data.get("_syllabus")
        course._created_at = datetime.fromisoformat(data["created_at"])
        course._updated_at = datetime.fromisoformat(data["updated_at"])
        course._version = data["version"]
        _status_raw = data.get("status")
        if isinstance(_status_raw, EntityStatus):
            course._status = _status_raw
        elif _status_raw is None:
            course._status = EntityStatus.ACTIVE
        else:
            try:
                course._status = EntityStatus(_status_raw)
            except Exception:
                try:
                    course._status = EntityStatus[_status_raw]
                except Exception:
                    course._status = EntityStatus.ACTIVE
        course._metadata = data.get("metadata", {})
        
        return course
    
    def find_by_course_code(self, course_code: str) -> Optional[Course]:
        """Find course by course code."""
        courses = self.find_all()
        for course in courses:
            if course.course_code == course_code:
                return course
        return None
    
    def find_by_department(self, department: str) -> List[Course]:
        """Find courses by department."""
        courses = self.find_all()
        return [c for c in courses if c.department == department]
    
    def find_by_credits(self, credits: int) -> List[Course]:
        """Find courses by credit hours."""
        courses = self.find_all()
        return [c for c in courses if c.credits == credits]


class SectionRepository(BaseRepository[Section]):
    """Repository for Section entities."""
    
    def __init__(self, database: DatabaseManager):
        super().__init__(database, "section")
    
    def _entity_from_dict(self, data: Dict[str, Any]) -> Section:
        """Convert dictionary to Section instance."""
        section = Section(
            course_id=data["_course_id"],
            section_number=data["_section_number"],
            semester=data["_semester"],
            year=data["_year"],
            instructor_id=data["_instructor_id"],
            entity_id=data["id"]
        )
        
        # Restore additional properties
        section._room_id = data.get("_room_id")
        section._schedule = data.get("_schedule", {})
        section._capacity = data.get("_capacity", 0)
        section._enrolled = set(data.get("_enrolled", []))
        section._waitlist = data.get("_waitlist", [])
        section._enrollment_policy = data.get("_enrollment_policy")
        section._created_at = datetime.fromisoformat(data["created_at"])
        section._updated_at = datetime.fromisoformat(data["updated_at"])
        section._version = data["version"]
        _status_raw = data.get("status")
        if isinstance(_status_raw, EntityStatus):
            section._status = _status_raw
        elif _status_raw is None:
            section._status = EntityStatus.ACTIVE
        else:
            try:
                section._status = EntityStatus(_status_raw)
            except Exception:
                try:
                    section._status = EntityStatus[_status_raw]
                except Exception:
                    section._status = EntityStatus.ACTIVE
        section._metadata = data.get("metadata", {})
        
        return section
    
    def find_by_course(self, course_id: str) -> List[Section]:
        """Find sections by course ID."""
        sections = self.find_all()
        return [s for s in sections if s.course_id == course_id]
    
    def find_by_instructor(self, instructor_id: str) -> List[Section]:
        """Find sections by instructor ID."""
        sections = self.find_all()
        return [s for s in sections if s.instructor_id == instructor_id]
    
    def find_by_semester_year(self, semester: str, year: int) -> List[Section]:
        """Find sections by semester and year."""
        sections = self.find_all()
        return [s for s in sections if s.semester == semester and s.year == year]
    
    def find_by_room(self, room_id: str) -> List[Section]:
        """Find sections by room ID."""
        sections = self.find_all()
        return [s for s in sections if s.room_id == room_id]


class GradeRepository(BaseRepository[Grade]):
    """Repository for Grade entities."""
    
    def __init__(self, database: DatabaseManager):
        super().__init__(database, "grade")
    
    def _entity_from_dict(self, data: Dict[str, Any]) -> Grade:
        """Convert dictionary to Grade instance."""
        grade = Grade(
            student_id=data["_student_id"],
            section_id=data["_section_id"],
            assessment_id=data["_assessment_id"],
            grade_value=data["_grade_value"],
            letter_grade=data["_letter_grade"],
            percentage=data["_percentage"],
            entity_id=data["id"]
        )
        
        # Restore additional properties
        grade._graded_at = datetime.fromisoformat(data["_graded_at"])
        grade._grader_id = data.get("_grader_id")
        grade._comments = data.get("_comments", "")
        grade._created_at = datetime.fromisoformat(data["created_at"])
        grade._updated_at = datetime.fromisoformat(data["updated_at"])
        grade._version = data["version"]
        _status_raw = data.get("status")
        if isinstance(_status_raw, EntityStatus):
            grade._status = _status_raw
        elif _status_raw is None:
            grade._status = EntityStatus.ACTIVE
        else:
            try:
                grade._status = EntityStatus(_status_raw)
            except Exception:
                try:
                    grade._status = EntityStatus[_status_raw]
                except Exception:
                    grade._status = EntityStatus.ACTIVE
        grade._metadata = data.get("metadata", {})
        
        return grade
    
    def find_by_student(self, student_id: str) -> List[Grade]:
        """Find grades by student ID."""
        grades = self.find_all()
        return [g for g in grades if g.student_id == student_id]
    
    def find_by_section(self, section_id: str) -> List[Grade]:
        """Find grades by section ID."""
        grades = self.find_all()
        return [g for g in grades if g.section_id == section_id]
    
    def find_by_grader(self, grader_id: str) -> List[Grade]:
        """Find grades by grader ID."""
        grades = self.find_all()
        return [g for g in grades if g.grader_id == grader_id]
    
    def find_by_grade_range(self, min_percentage: float, max_percentage: float) -> List[Grade]:
        """Find grades within a percentage range."""
        grades = self.find_all()
        return [g for g in grades if min_percentage <= g.percentage <= max_percentage]


class FacilityRepository(BaseRepository[Facility]):
    """Repository for Facility entities."""
    
    def __init__(self, database: DatabaseManager):
        super().__init__(database, "facility")
    
    def _entity_from_dict(self, data: Dict[str, Any]) -> Facility:
        """Convert dictionary to Facility instance."""
        from ..core.enums import AccessLevel
        
        facility = Facility(
            name=data["_name"],
            facility_type=data["_facility_type"],
            location=data["_location"],
            entity_id=data["id"]
        )
        
        # Restore additional properties
        facility._rooms = set(data.get("_rooms", []))
        facility._access_level = AccessLevel(data.get("_access_level", "read"))
        facility._security_zones = set(data.get("_security_zones", []))
        facility._created_at = datetime.fromisoformat(data["created_at"])
        facility._updated_at = datetime.fromisoformat(data["updated_at"])
        facility._version = data["version"]
        _status_raw = data.get("status")
        if isinstance(_status_raw, EntityStatus):
            facility._status = _status_raw
        elif _status_raw is None:
            facility._status = EntityStatus.ACTIVE
        else:
            try:
                facility._status = EntityStatus(_status_raw)
            except Exception:
                try:
                    facility._status = EntityStatus[_status_raw]
                except Exception:
                    facility._status = EntityStatus.ACTIVE
        facility._metadata = data.get("metadata", {})
        
        return facility
    
    def find_by_name(self, name: str) -> Optional[Facility]:
        """Find facility by name."""
        facilities = self.find_all()
        for facility in facilities:
            if facility.name == name:
                return facility
        return None
    
    def find_by_type(self, facility_type: str) -> List[Facility]:
        """Find facilities by type."""
        facilities = self.find_all()
        return [f for f in facilities if f.facility_type == facility_type]
    
    def find_by_location(self, location: str) -> List[Facility]:
        """Find facilities by location."""
        facilities = self.find_all()
        return [f for f in facilities if f.location == location]


class RoomRepository(BaseRepository[Room]):
    """Repository for Room entities."""
    
    def __init__(self, database: DatabaseManager):
        super().__init__(database, "room")
    
    def _entity_from_dict(self, data: Dict[str, Any]) -> Room:
        """Convert dictionary to Room instance."""
        room = Room(
            room_number=data["_room_number"],
            facility_id=data["_facility_id"],
            room_type=data["_room_type"],
            capacity=data["_capacity"],
            entity_id=data["id"]
        )
        
        # Restore additional properties
        room._equipment = set(data.get("_equipment", []))
        room._access_control = data.get("_access_control", False)
        room._booking_schedule = data.get("_booking_schedule", {})
        room._created_at = datetime.fromisoformat(data["created_at"])
        room._updated_at = datetime.fromisoformat(data["updated_at"])
        room._version = data["version"]
        _status_raw = data.get("status")
        if isinstance(_status_raw, EntityStatus):
            room._status = _status_raw
        elif _status_raw is None:
            room._status = EntityStatus.ACTIVE
        else:
            try:
                room._status = EntityStatus(_status_raw)
            except Exception:
                try:
                    room._status = EntityStatus[_status_raw]
                except Exception:
                    room._status = EntityStatus.ACTIVE
        room._metadata = data.get("metadata", {})
        
        return room
    
    def find_by_facility(self, facility_id: str) -> List[Room]:
        """Find rooms by facility ID."""
        rooms = self.find_all()
        return [r for r in rooms if r.facility_id == facility_id]
    
    def find_by_type(self, room_type: str) -> List[Room]:
        """Find rooms by type."""
        rooms = self.find_all()
        return [r for r in rooms if r.room_type == room_type]
    
    def find_by_capacity_range(self, min_capacity: int, max_capacity: int) -> List[Room]:
        """Find rooms within a capacity range."""
        rooms = self.find_all()
        return [r for r in rooms if min_capacity <= r.capacity <= max_capacity]
    
    def find_available_rooms(self, start_time: datetime, end_time: datetime) -> List[Room]:
        """Find rooms available during a time period."""
        # This would implement more sophisticated availability checking
        rooms = self.find_all()
        available_rooms = []
        
        for room in rooms:
            # Simple availability check - in practice, this would be more complex
            is_available = True
            for booking_key, booking in room.booking_schedule.items():
                booking_start = datetime.fromisoformat(booking['start_time'])
                booking_end = datetime.fromisoformat(booking['end_time'])
                
                if (start_time < booking_end and end_time > booking_start):
                    is_available = False
                    break
            
            if is_available:
                available_rooms.append(room)
        
        return available_rooms
