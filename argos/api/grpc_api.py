"""
gRPC API implementation for the Argos platform.
"""

import json
import threading
import grpc
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from . import argos_pb2, argos_pb2_grpc
from ..core.entities import Student, Lecturer, Course, Section, Grade, Facility, Room
from ..core.enums import PersonType, GradeLevel, EventType
from ..core.exceptions import ValidationError, EnrollmentError, SchedulingError
from ..services import EnrollmentService, SchedulerService, EventService
from ..persistence import DatabaseManager, StudentRepository, CourseRepository, SectionRepository


class ArgosGrpcService(argos_pb2_grpc.ArgosServiceServicer):
    """gRPC service implementation for Argos platform."""
    
    def __init__(self, database: DatabaseManager, enrollment_service: EnrollmentService,
                 scheduler_service: SchedulerService, event_service: EventService):
        self._database = database
        self._enrollment_service = enrollment_service
        self._scheduler_service = scheduler_service
        self._event_service = event_service
        
        # Initialize repositories
        self._student_repo = StudentRepository(database)
        self._course_repo = CourseRepository(database)
        self._section_repo = SectionRepository(database)
        
        self._lock = threading.RLock()
    
    def CreateStudent(self, request, context):
        """Create a new student."""
        try:
            with self._lock:
                # Create student entity
                student = Student(
                    first_name=request.first_name,
                    last_name=request.last_name,
                    email=request.email,
                    student_id=request.student_id,
                    grade_level=GradeLevel(request.grade_level)
                )
                
                # Save to database
                saved_student = self._student_repo.save(student)
                
                # Convert to protobuf
                student_pb = self._student_to_protobuf(saved_student)
                
                return argos_pb2.CreateStudentResponse(
                    success=True,
                    message="Student created successfully",
                    student=student_pb
                )
        
        except ValidationError as e:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(str(e))
            return argos_pb2.CreateStudentResponse(
                success=False,
                message=f"Validation error: {str(e)}"
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return argos_pb2.CreateStudentResponse(
                success=False,
                message=f"Internal error: {str(e)}"
            )
    
    def GetStudent(self, request, context):
        """Get a student by ID."""
        try:
            with self._lock:
                student = self._student_repo.find_by_student_id(request.student_id)
                
                if not student:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    return argos_pb2.GetStudentResponse(
                        success=False,
                        message="Student not found"
                    )
                
                student_pb = self._student_to_protobuf(student)
                
                return argos_pb2.GetStudentResponse(
                    success=True,
                    message="Student retrieved successfully",
                    student=student_pb
                )
        
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return argos_pb2.GetStudentResponse(
                success=False,
                message=f"Internal error: {str(e)}"
            )
    
    def EnrollStudent(self, request, context):
        """Enroll a student in a section."""
        try:
            with self._lock:
                # Get student and section
                student = self._student_repo.find_by_student_id(request.student_id)
                section = self._section_repo.find_by_id(request.section_id)
                
                if not student:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    return argos_pb2.EnrollStudentResponse(
                        success=False,
                        message="Student not found"
                    )
                
                if not section:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    return argos_pb2.EnrollStudentResponse(
                        success=False,
                        message="Section not found"
                    )
                
                # Enroll student
                result = self._enrollment_service.enroll_student(student, section)
                
                if result.success:
                    return argos_pb2.EnrollStudentResponse(
                        success=True,
                        message=result.message,
                        status=result.status.value,
                        waitlist_position=result.waitlist_position
                    )
                else:
                    context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                    return argos_pb2.EnrollStudentResponse(
                        success=False,
                        message=result.message
                    )
        
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return argos_pb2.EnrollStudentResponse(
                success=False,
                message=f"Internal error: {str(e)}"
            )
    
    def GetEnrollments(self, request, context):
        """Get student enrollments."""
        try:
            with self._lock:
                enrollments = self._enrollment_service.get_enrollments(request.student_id)
                
                return argos_pb2.GetEnrollmentsResponse(
                    success=True,
                    message="Enrollments retrieved successfully",
                    section_ids=enrollments
                )
        
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return argos_pb2.GetEnrollmentsResponse(
                success=False,
                message=f"Internal error: {str(e)}"
            )
    
    def CreateCourse(self, request, context):
        """Create a new course."""
        try:
            with self._lock:
                # Create course entity
                course = Course(
                    course_code=request.course_code,
                    title=request.title,
                    description=request.description,
                    credits=request.credits,
                    department=request.department
                )
                
                # Add prerequisites
                for prereq in request.prerequisites:
                    course.add_prerequisite(prereq)
                
                # Save to database
                saved_course = self._course_repo.save(course)
                
                # Convert to protobuf
                course_pb = self._course_to_protobuf(saved_course)
                
                return argos_pb2.CreateCourseResponse(
                    success=True,
                    message="Course created successfully",
                    course=course_pb
                )
        
        except ValidationError as e:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(str(e))
            return argos_pb2.CreateCourseResponse(
                success=False,
                message=f"Validation error: {str(e)}"
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return argos_pb2.CreateCourseResponse(
                success=False,
                message=f"Internal error: {str(e)}"
            )
    
    def CreateSection(self, request, context):
        """Create a new section."""
        try:
            with self._lock:
                # Create section entity
                section = Section(
                    course_id=request.course_id,
                    section_number=request.section_number,
                    semester=request.semester,
                    year=request.year,
                    instructor_id=request.instructor_id
                )
                
                section.set_capacity(request.capacity)
                
                # Save to database
                saved_section = self._section_repo.save(section)
                
                # Convert to protobuf
                section_pb = self._section_to_protobuf(saved_section)
                
                return argos_pb2.CreateSectionResponse(
                    success=True,
                    message="Section created successfully",
                    section=section_pb
                )
        
        except ValidationError as e:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(str(e))
            return argos_pb2.CreateSectionResponse(
                success=False,
                message=f"Validation error: {str(e)}"
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return argos_pb2.CreateSectionResponse(
                success=False,
                message=f"Internal error: {str(e)}"
            )
    
    def ScheduleSection(self, request, context):
        """Schedule a section."""
        try:
            with self._lock:
                # Convert time slots
                time_slots = []
                for slot_pb in request.time_slots:
                    time_slot = {
                        'start_time': datetime.fromtimestamp(slot_pb.start_time / 1000),
                        'end_time': datetime.fromtimestamp(slot_pb.end_time / 1000),
                        'day_of_week': slot_pb.day_of_week
                    }
                    time_slots.append(time_slot)
                
                # Convert room requirements
                room_requirements = {
                    'min_capacity': request.room_requirements.min_capacity,
                    'room_type': request.room_requirements.room_type or None,
                    'equipment': list(request.room_requirements.equipment),
                    'access_control': request.room_requirements.access_control
                }
                
                # Create schedule request
                from ..services.scheduler_service import ScheduleRequest
                schedule_request = ScheduleRequest(
                    section_id=request.section_id,
                    time_slots=time_slots,
                    room_requirements=room_requirements,
                    constraints=list(request.constraints)
                )
                
                # Schedule section
                result = self._scheduler_service.schedule_section(schedule_request)
                
                if result.success:
                    # Convert assigned times back to protobuf
                    assigned_times = []
                    for slot in result.assigned_times:
                        assigned_times.append(argos_pb2.TimeSlot(
                            start_time=int(slot['start_time'].timestamp() * 1000),
                            end_time=int(slot['end_time'].timestamp() * 1000),
                            day_of_week=slot['day_of_week']
                        ))
                    
                    return argos_pb2.ScheduleSectionResponse(
                        success=True,
                        message=result.message,
                        schedule_id=result.schedule_id,
                        assigned_room=result.assigned_room,
                        assigned_times=assigned_times,
                        conflicts=result.conflicts
                    )
                else:
                    context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                    return argos_pb2.ScheduleSectionResponse(
                        success=False,
                        message=result.message,
                        conflicts=result.conflicts
                    )
        
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return argos_pb2.ScheduleSectionResponse(
                success=False,
                message=f"Internal error: {str(e)}"
            )
    
    def GetSchedule(self, request, context):
        """Get section schedule."""
        try:
            with self._lock:
                # This would integrate with the scheduler service
                # For now, return a simple response
                return argos_pb2.GetScheduleResponse(
                    success=True,
                    message="Schedule retrieved successfully"
                )
        
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return argos_pb2.GetScheduleResponse(
                success=False,
                message=f"Internal error: {str(e)}"
            )
    
    def GetMLPrediction(self, request, context):
        """Get ML prediction."""
        try:
            with self._lock:
                # This would integrate with ML services
                # For now, return a mock response
                prediction = {"prediction": "mock_prediction", "confidence": 0.85}
                explanation = {"explanation": "mock_explanation"}
                
                return argos_pb2.MLPredictionResponse(
                    success=True,
                    message="Prediction generated successfully",
                    prediction=json.dumps(prediction),
                    explanation=json.dumps(explanation)
                )
        
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return argos_pb2.MLPredictionResponse(
                success=False,
                message=f"Internal error: {str(e)}"
            )
    
    def GetStatistics(self, request, context):
        """Get system statistics."""
        try:
            with self._lock:
                # Get statistics from services
                enrollment_stats = self._enrollment_service.get_statistics()
                scheduler_stats = self._scheduler_service.get_statistics()
                event_stats = self._event_service.get_processing_statistics()
                
                statistics = {
                    "enrollment": enrollment_stats,
                    "scheduler": scheduler_stats,
                    "events": event_stats
                }
                
                return argos_pb2.GetStatisticsResponse(
                    success=True,
                    message="Statistics retrieved successfully",
                    statistics=json.dumps(statistics)
                )
        
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return argos_pb2.GetStatisticsResponse(
                success=False,
                message=f"Internal error: {str(e)}"
            )
    
    def _student_to_protobuf(self, student: Student) -> argos_pb2.Student:
        """Convert Student entity to protobuf."""
        person = argos_pb2.Person(
            id=student.id,
            first_name=student.first_name,
            last_name=student.last_name,
            email=student.email,
            person_type=argos_pb2.PersonType.Value(student.person_type.name),
            roles=list(student.roles),
            created_at=int(student.created_at.timestamp() * 1000),
            updated_at=int(student.updated_at.timestamp() * 1000),
            version=student.version,
            status=student.status.value
        )
        
        return argos_pb2.Student(
            person=person,
            student_id=student.student_id,
            grade_level=student.grade_level.value,
            gpa=student.gpa,
            academic_standing=student.academic_standing,
            advisor=student.advisor or "",
            enrollments=list(student.enrollments)
        )
    
    def _course_to_protobuf(self, course: Course) -> argos_pb2.Course:
        """Convert Course entity to protobuf."""
        return argos_pb2.Course(
            id=course.id,
            course_code=course.course_code,
            title=course.title,
            description=course.description,
            credits=course.credits,
            department=course.department,
            prerequisites=list(course.prerequisites),
            sections=list(course.sections),
            syllabus=course.syllabus or "",
            created_at=int(course.created_at.timestamp() * 1000),
            updated_at=int(course.updated_at.timestamp() * 1000),
            version=course.version,
            status=course.status.value
        )
    
    def _section_to_protobuf(self, section: Section) -> argos_pb2.Section:
        """Convert Section entity to protobuf."""
        return argos_pb2.Section(
            id=section.id,
            course_id=section.course_id,
            section_number=section.section_number,
            semester=section.semester,
            year=section.year,
            instructor_id=section.instructor_id,
            room_id=section.room_id or "",
            schedule=section.schedule,
            capacity=section.capacity,
            enrolled=list(section.enrolled),
            waitlist=list(section.waitlist),
            enrollment_policy=section.enrollment_policy or "",
            created_at=int(section.created_at.timestamp() * 1000),
            updated_at=int(section.updated_at.timestamp() * 1000),
            version=section.version,
            status=section.status.value
        )
