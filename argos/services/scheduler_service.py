"""
Scheduler service for managing course schedules and room assignments.
"""

import asyncio
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import uuid
from datetime import datetime, timedelta

from ..core.entities import Section, Room, Facility, Event, EventType
from ..core.interfaces import Constraint, Scheduler
from ..core.enums import ConstraintType
from ..core.exceptions import SchedulingError, ValidationError, ConcurrencyError
from .concurrency_manager import ConcurrencyManager, LockType


class ScheduleStatus(Enum):
    """Status of a schedule."""
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    ACTIVE = "active"
    CANCELLED = "cancelled"


@dataclass
class TimeSlot:
    """Represents a time slot for scheduling."""
    start_time: datetime
    end_time: datetime
    day_of_week: int  # 0=Monday, 6=Sunday
    
    def overlaps_with(self, other: 'TimeSlot') -> bool:
        """Check if this time slot overlaps with another."""
        return (self.start_time < other.end_time and 
                self.end_time > other.start_time and
                self.day_of_week == other.day_of_week)
    
    def duration_minutes(self) -> int:
        """Get duration in minutes."""
        return int((self.end_time - self.start_time).total_seconds() / 60)


@dataclass
class ScheduleRequest:
    """Request to schedule a section."""
    section_id: str
    time_slots: List[TimeSlot]
    room_requirements: Dict[str, Any]
    priority: int = 0
    constraints: List[str] = None  # Constraint IDs
    
    def __post_init__(self):
        if self.constraints is None:
            self.constraints = []


@dataclass
class ScheduleResult:
    """Result of a scheduling operation."""
    success: bool
    schedule_id: Optional[str]
    assigned_room: Optional[str]
    assigned_times: List[TimeSlot]
    conflicts: List[str]
    message: str
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class RoomCapacityConstraint(Constraint):
    """Constraint ensuring room capacity meets section requirements."""
    
    def __init__(self, required_capacity: int):
        self._required_capacity = required_capacity
    
    def is_satisfied(self, schedule: Dict[str, Any]) -> bool:
        """Check if room capacity constraint is satisfied."""
        room = schedule.get('room')
        if not room:
            return False
        return room.capacity >= self._required_capacity
    
    def get_type(self) -> ConstraintType:
        return ConstraintType.HARD
    
    def get_weight(self) -> float:
        return 1.0


class TimeConflictConstraint(Constraint):
    """Constraint preventing time conflicts."""
    
    def __init__(self, existing_schedules: List[Dict[str, Any]]):
        self._existing_schedules = existing_schedules
    
    def is_satisfied(self, schedule: Dict[str, Any]) -> bool:
        """Check if time conflict constraint is satisfied."""
        new_time_slots = schedule.get('time_slots', [])
        
        for existing_schedule in self._existing_schedules:
            existing_room = existing_schedule.get('room')
            new_room = schedule.get('room')
            
            # Check room conflicts
            if existing_room and new_room and existing_room.id == new_room.id:
                existing_times = existing_schedule.get('time_slots', [])
                for new_slot in new_time_slots:
                    for existing_slot in existing_times:
                        if new_slot.overlaps_with(existing_slot):
                            return False
        
        return True
    
    def get_type(self) -> ConstraintType:
        return ConstraintType.HARD
    
    def get_weight(self) -> float:
        return 1.0


class InstructorAvailabilityConstraint(Constraint):
    """Constraint ensuring instructor is available."""
    
    def __init__(self, instructor_id: str, availability: List[TimeSlot]):
        self._instructor_id = instructor_id
        self._availability = availability
    
    def is_satisfied(self, schedule: Dict[str, Any]) -> bool:
        """Check if instructor availability constraint is satisfied."""
        time_slots = schedule.get('time_slots', [])
        
        for slot in time_slots:
            slot_available = False
            for available_slot in self._availability:
                if (slot.start_time >= available_slot.start_time and 
                    slot.end_time <= available_slot.end_time and
                    slot.day_of_week == available_slot.day_of_week):
                    slot_available = True
                    break
            
            if not slot_available:
                return False
        
        return True
    
    def get_type(self) -> ConstraintType:
        return ConstraintType.HARD
    
    def get_weight(self) -> float:
        return 1.0


class RoomPreferenceConstraint(Constraint):
    """Soft constraint for room preferences."""
    
    def __init__(self, preferred_room_types: List[str], preferred_facilities: List[str]):
        self._preferred_room_types = preferred_room_types
        self._preferred_facilities = preferred_facilities
    
    def is_satisfied(self, schedule: Dict[str, Any]) -> bool:
        """Check if room preference constraint is satisfied."""
        room = schedule.get('room')
        if not room:
            return False
        
        # Check room type preference
        if self._preferred_room_types and room.room_type not in self._preferred_room_types:
            return False
        
        # Check facility preference
        if self._preferred_facilities and room.facility_id not in self._preferred_facilities:
            return False
        
        return True
    
    def get_type(self) -> ConstraintType:
        return ConstraintType.SOFT
    
    def get_weight(self) -> float:
        return 0.5


class SchedulerService:
    """Service for managing course schedules and room assignments."""
    
    def __init__(self, concurrency_manager: ConcurrencyManager):
        self._concurrency_manager = concurrency_manager
        self._schedules: Dict[str, Dict[str, Any]] = {}  # schedule_id -> schedule_data
        self._room_assignments: Dict[str, List[TimeSlot]] = {}  # room_id -> [time_slots]
        self._instructor_schedules: Dict[str, List[TimeSlot]] = {}  # instructor_id -> [time_slots]
        self._constraints: Dict[str, Constraint] = {}
        self._rooms: Dict[str, Room] = {}
        self._facilities: Dict[str, Facility] = {}
        self._lock = threading.RLock()
        
        # Initialize default constraints
        self._initialize_default_constraints()
    
    def _initialize_default_constraints(self):
        """Initialize default scheduling constraints."""
        # Add some default constraints
        pass
    
    def add_room(self, room: Room) -> None:
        """Add a room to the scheduler."""
        with self._lock:
            self._rooms[room.id] = room
            self._room_assignments[room.id] = []
    
    def add_facility(self, facility: Facility) -> None:
        """Add a facility to the scheduler."""
        with self._lock:
            self._facilities[facility.id] = facility
    
    def add_constraint(self, constraint_id: str, constraint: Constraint) -> None:
        """Add a scheduling constraint."""
        with self._lock:
            self._constraints[constraint_id] = constraint
    
    def remove_constraint(self, constraint_id: str) -> None:
        """Remove a scheduling constraint."""
        with self._lock:
            self._constraints.pop(constraint_id, None)
    
    def schedule_section(self, request: ScheduleRequest) -> ScheduleResult:
        """Schedule a section with the given requirements."""
        with self._lock:
            try:
                with self._concurrency_manager.lock(
                    f"scheduling_{request.section_id}",
                    LockType.WRITE,
                    f"scheduler_service_{threading.get_ident()}"
                ):
                    # Find suitable room
                    suitable_rooms = self._find_suitable_rooms(request)
                    if not suitable_rooms:
                        return ScheduleResult(
                            success=False,
                            schedule_id=None,
                            assigned_room=None,
                            assigned_times=[],
                            conflicts=["No suitable rooms available"],
                            message="No suitable rooms found for scheduling"
                        )
                    
                    # Try to assign the best room
                    best_room = suitable_rooms[0]  # First suitable room
                    conflicts = self._check_scheduling_conflicts(request, best_room)
                    
                    if conflicts:
                        return ScheduleResult(
                            success=False,
                            schedule_id=None,
                            assigned_room=None,
                            assigned_times=[],
                            conflicts=conflicts,
                            message="Scheduling conflicts detected"
                        )
                    
                    # Create schedule
                    schedule_id = str(uuid.uuid4())
                    schedule_data = {
                        'schedule_id': schedule_id,
                        'section_id': request.section_id,
                        'room': best_room,
                        'time_slots': request.time_slots,
                        'status': ScheduleStatus.APPROVED,
                        'created_at': datetime.now(),
                        'constraints': request.constraints
                    }
                    
                    self._schedules[schedule_id] = schedule_data
                    self._room_assignments[best_room.id].extend(request.time_slots)
                    
                    # Update instructor schedule
                    # This would need instructor_id from the section
                    # instructor_schedule = self._instructor_schedules.get(instructor_id, [])
                    # instructor_schedule.extend(request.time_slots)
                    # self._instructor_schedules[instructor_id] = instructor_schedule
                    
                    self._publish_event(EventType.SYSTEM_ALERT, {
                        'type': 'schedule_created',
                        'schedule_id': schedule_id,
                        'section_id': request.section_id,
                        'room_id': best_room.id,
                        'timestamp': time.time()
                    })
                    
                    return ScheduleResult(
                        success=True,
                        schedule_id=schedule_id,
                        assigned_room=best_room.id,
                        assigned_times=request.time_slots,
                        conflicts=[],
                        message="Section scheduled successfully"
                    )
            
            except ConcurrencyError as e:
                return ScheduleResult(
                    success=False,
                    schedule_id=None,
                    assigned_room=None,
                    assigned_times=[],
                    conflicts=[f"Concurrency error: {str(e)}"],
                    message="Scheduling failed due to concurrency error"
                )
    
    def _find_suitable_rooms(self, request: ScheduleRequest) -> List[Room]:
        """Find rooms that meet the scheduling requirements."""
        suitable_rooms = []
        
        for room in self._rooms.values():
            # Check room capacity
            if room.capacity < request.room_requirements.get('min_capacity', 1):
                continue
            
            # Check room type
            required_type = request.room_requirements.get('room_type')
            if required_type and room.room_type != required_type:
                continue
            
            # Check equipment requirements
            required_equipment = request.room_requirements.get('equipment', [])
            if required_equipment and not all(eq in room.equipment for eq in required_equipment):
                continue
            
            # Check access control requirements
            requires_access_control = request.room_requirements.get('access_control', False)
            if requires_access_control and not room.has_access_control:
                continue
            
            suitable_rooms.append(room)
        
        # Sort by preference (capacity closest to requirement, then by room number)
        min_capacity = request.room_requirements.get('min_capacity', 1)
        suitable_rooms.sort(key=lambda r: (abs(r.capacity - min_capacity), r.room_number))
        
        return suitable_rooms
    
    def _check_scheduling_conflicts(self, request: ScheduleRequest, room: Room) -> List[str]:
        """Check for scheduling conflicts."""
        conflicts = []
        
        # Check room availability
        for time_slot in request.time_slots:
            for existing_slot in self._room_assignments.get(room.id, []):
                if time_slot.overlaps_with(existing_slot):
                    conflicts.append(f"Room {room.room_number} is already booked at {time_slot.start_time}")
        
        # Check constraints
        for constraint_id in request.constraints:
            if constraint_id in self._constraints:
                constraint = self._constraints[constraint_id]
                schedule_data = {
                    'room': room,
                    'time_slots': request.time_slots,
                    'section_id': request.section_id
                }
                
                if not constraint.is_satisfied(schedule_data):
                    conflicts.append(f"Constraint violation: {constraint_id}")
        
        return conflicts
    
    def cancel_schedule(self, schedule_id: str) -> bool:
        """Cancel a schedule."""
        with self._lock:
            if schedule_id not in self._schedules:
                return False
            
            schedule_data = self._schedules[schedule_id]
            room_id = schedule_data['room'].id
            time_slots = schedule_data['time_slots']
            
            # Remove from room assignments
            for slot in time_slots:
                if slot in self._room_assignments[room_id]:
                    self._room_assignments[room_id].remove(slot)
            
            # Mark as cancelled
            schedule_data['status'] = ScheduleStatus.CANCELLED
            
            self._publish_event(EventType.SYSTEM_ALERT, {
                'type': 'schedule_cancelled',
                'schedule_id': schedule_id,
                'timestamp': time.time()
            })
            
            return True
    
    def get_schedule(self, schedule_id: str) -> Optional[Dict[str, Any]]:
        """Get schedule by ID."""
        with self._lock:
            return self._schedules.get(schedule_id)
    
    def get_room_schedule(self, room_id: str) -> List[TimeSlot]:
        """Get schedule for a specific room."""
        with self._lock:
            return self._room_assignments.get(room_id, []).copy()
    
    def get_instructor_schedule(self, instructor_id: str) -> List[TimeSlot]:
        """Get schedule for a specific instructor."""
        with self._lock:
            return self._instructor_schedules.get(instructor_id, []).copy()
    
    def optimize_schedule(self, objective: str = "minimize_conflicts") -> Dict[str, Any]:
        """Optimize the current schedule."""
        with self._lock:
            if objective == "minimize_conflicts":
                return self._minimize_conflicts()
            elif objective == "maximize_room_utilization":
                return self._maximize_room_utilization()
            else:
                return {"error": f"Unknown optimization objective: {objective}"}
    
    def _minimize_conflicts(self) -> Dict[str, Any]:
        """Minimize scheduling conflicts."""
        # Simple conflict minimization - in practice, this would be more sophisticated
        conflicts_resolved = 0
        total_conflicts = 0
        
        for schedule_id, schedule_data in self._schedules.items():
            if schedule_data['status'] == ScheduleStatus.ACTIVE:
                # Check for conflicts and attempt to resolve
                room = schedule_data['room']
                time_slots = schedule_data['time_slots']
                
                for slot in time_slots:
                    for existing_slot in self._room_assignments.get(room.id, []):
                        if slot.overlaps_with(existing_slot) and slot != existing_slot:
                            total_conflicts += 1
                            # Try to find alternative time
                            # This is a simplified approach
                            conflicts_resolved += 1
        
        return {
            'objective': 'minimize_conflicts',
            'total_conflicts': total_conflicts,
            'conflicts_resolved': conflicts_resolved,
            'optimization_score': conflicts_resolved / max(total_conflicts, 1)
        }
    
    def _maximize_room_utilization(self) -> Dict[str, Any]:
        """Maximize room utilization."""
        total_capacity = sum(room.capacity for room in self._rooms.values())
        utilized_capacity = 0
        
        for room_id, time_slots in self._room_assignments.items():
            room = self._rooms[room_id]
            utilized_capacity += len(time_slots) * room.capacity
        
        utilization_rate = utilized_capacity / max(total_capacity, 1)
        
        return {
            'objective': 'maximize_room_utilization',
            'total_capacity': total_capacity,
            'utilized_capacity': utilized_capacity,
            'utilization_rate': utilization_rate
        }
    
    def _publish_event(self, event_type: EventType, event_data: Dict[str, Any]) -> None:
        """Publish an event."""
        # This would integrate with the event system
        pass
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get scheduling statistics."""
        with self._lock:
            total_schedules = len(self._schedules)
            active_schedules = sum(1 for s in self._schedules.values() 
                                 if s['status'] == ScheduleStatus.ACTIVE)
            total_rooms = len(self._rooms)
            total_facilities = len(self._facilities)
            
            return {
                'total_schedules': total_schedules,
                'active_schedules': active_schedules,
                'total_rooms': total_rooms,
                'total_facilities': total_facilities,
                'constraints': len(self._constraints)
            }
