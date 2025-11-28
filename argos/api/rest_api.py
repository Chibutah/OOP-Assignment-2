"""
REST API implementation for the Argos platform using FastAPI.
"""

import json
import threading
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..core.entities import Student, Lecturer, Course, Section, Grade, Facility, Room
from ..core.enums import PersonType, GradeLevel, EventType
from ..core.exceptions import ValidationError, EnrollmentError, SchedulingError
from ..services import EnrollmentService, SchedulerService, EventService
from ..persistence import DatabaseManager, StudentRepository, CourseRepository, SectionRepository


# Pydantic models for API
class StudentCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., pattern=r'^[^@]+@[^@]+\.[^@]+$')
    student_id: str = Field(..., min_length=1, max_length=20)
    grade_level: str = Field(..., pattern=r'^(freshman|sophomore|junior|senior|graduate|postgraduate)$')


class StudentResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: str
    student_id: str
    grade_level: str
    gpa: Optional[float] = None
    academic_standing: str
    advisor: Optional[str] = None
    enrollments: List[str] = []
    created_at: datetime
    updated_at: datetime
    version: int
    status: str


class CourseCreate(BaseModel):
    course_code: str = Field(..., min_length=1, max_length=20)
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=1000)
    credits: int = Field(..., ge=1, le=10)
    department: str = Field(..., min_length=1, max_length=100)
    prerequisites: List[str] = []


class CourseResponse(BaseModel):
    id: str
    course_code: str
    title: str
    description: str
    credits: int
    department: str
    prerequisites: List[str] = []
    sections: List[str] = []
    syllabus: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    version: int
    status: str


class SectionCreate(BaseModel):
    course_id: str = Field(..., min_length=1)
    section_number: str = Field(..., min_length=1, max_length=10)
    semester: str = Field(..., min_length=1, max_length=20)
    year: int = Field(..., ge=2020, le=2030)
    instructor_id: str = Field(..., min_length=1)
    capacity: int = Field(..., ge=1, le=500)


class SectionResponse(BaseModel):
    id: str
    course_id: str
    section_number: str
    semester: str
    year: int
    instructor_id: str
    room_id: Optional[str] = None
    schedule: Dict[str, str] = {}
    capacity: int
    enrolled_count: int
    waitlist_count: int
    is_full: bool
    created_at: datetime
    updated_at: datetime
    version: int
    status: str


class EnrollmentRequest(BaseModel):
    student_id: str = Field(..., min_length=1)
    section_id: str = Field(..., min_length=1)


class EnrollmentResponse(BaseModel):
    success: bool
    message: str
    status: str
    waitlist_position: Optional[int] = None


class ScheduleRequest(BaseModel):
    section_id: str = Field(..., min_length=1)
    time_slots: List[Dict[str, Any]] = Field(..., min_items=1)
    room_requirements: Dict[str, Any] = Field(default_factory=dict)
    constraints: List[str] = Field(default_factory=list)


class ScheduleResponse(BaseModel):
    success: bool
    message: str
    schedule_id: Optional[str] = None
    assigned_room: Optional[str] = None
    assigned_times: List[Dict[str, Any]] = []
    conflicts: List[str] = []


class MLPredictionRequest(BaseModel):
    model_type: str = Field(..., min_length=1)
    input_data: Dict[str, Any] = Field(..., min_items=1)


class MLPredictionResponse(BaseModel):
    success: bool
    message: str
    prediction: Dict[str, Any]
    explanation: Dict[str, Any]


class StatisticsResponse(BaseModel):
    success: bool
    message: str
    statistics: Dict[str, Any]


class ArgosRestAPI:
    """REST API implementation for Argos platform."""
    
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
        
        # Create FastAPI app
        self.app = FastAPI(
            title="Argos Campus Management API",
            description="A federated, adaptive smart campus orchestration platform",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Setup routes
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup API routes."""
        
        @self.app.get("/", response_model=Dict[str, str])
        async def root():
            """Root endpoint."""
            return {
                "message": "Argos Campus Management API",
                "version": "1.0.0",
                "docs": "/docs"
            }
        
        @self.app.get("/health", response_model=Dict[str, str])
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}
        
        # Student endpoints
        @self.app.post("/students", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
        async def create_student(student_data: StudentCreate):
            """Create a new student."""
            try:
                with self._lock:
                    # Create student entity
                    student = Student(
                        first_name=student_data.first_name,
                        last_name=student_data.last_name,
                        email=student_data.email,
                        student_id=student_data.student_id,
                        grade_level=GradeLevel(student_data.grade_level)
                    )
                    
                    # Save to database
                    saved_student = self._student_repo.save(student)
                    
                    return self._student_to_response(saved_student)
            
            except ValidationError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
        
        @self.app.get("/students/{student_id}", response_model=StudentResponse)
        async def get_student(student_id: str):
            """Get a student by student ID."""
            try:
                with self._lock:
                    student = self._student_repo.find_by_student_id(student_id)
                    
                    if not student:
                        raise HTTPException(status_code=404, detail="Student not found")
                    
                    return self._student_to_response(student)
            
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
        
        @self.app.get("/students", response_model=List[StudentResponse])
        async def list_students(skip: int = 0, limit: int = 100):
            """List all students."""
            try:
                with self._lock:
                    students = self._student_repo.find_all()
                    
                    # Apply pagination
                    students = students[skip:skip + limit]
                    
                    return [self._student_to_response(student) for student in students]
            
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
        
        # Course endpoints
        @self.app.post("/courses", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
        async def create_course(course_data: CourseCreate):
            """Create a new course."""
            try:
                with self._lock:
                    # Create course entity
                    course = Course(
                        course_code=course_data.course_code,
                        title=course_data.title,
                        description=course_data.description,
                        credits=course_data.credits,
                        department=course_data.department
                    )
                    
                    # Add prerequisites
                    for prereq in course_data.prerequisites:
                        course.add_prerequisite(prereq)
                    
                    # Save to database
                    saved_course = self._course_repo.save(course)
                    
                    return self._course_to_response(saved_course)
            
            except ValidationError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
        
        @self.app.get("/courses/{course_id}", response_model=CourseResponse)
        async def get_course(course_id: str):
            """Get a course by ID."""
            try:
                with self._lock:
                    course = self._course_repo.find_by_id(course_id)
                    
                    if not course:
                        raise HTTPException(status_code=404, detail="Course not found")
                    
                    return self._course_to_response(course)
            
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
        
        @self.app.get("/courses", response_model=List[CourseResponse])
        async def list_courses(skip: int = 0, limit: int = 100):
            """List all courses."""
            try:
                with self._lock:
                    courses = self._course_repo.find_all()
                    
                    # Apply pagination
                    courses = courses[skip:skip + limit]
                    
                    return [self._course_to_response(course) for course in courses]
            
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
        
        # Section endpoints
        @self.app.post("/sections", response_model=SectionResponse, status_code=status.HTTP_201_CREATED)
        async def create_section(section_data: SectionCreate):
            """Create a new section."""
            try:
                with self._lock:
                    # Create section entity
                    section = Section(
                        course_id=section_data.course_id,
                        section_number=section_data.section_number,
                        semester=section_data.semester,
                        year=section_data.year,
                        instructor_id=section_data.instructor_id
                    )
                    
                    section.set_capacity(section_data.capacity)
                    
                    # Save to database
                    saved_section = self._section_repo.save(section)
                    
                    return self._section_to_response(saved_section)
            
            except ValidationError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
        
        @self.app.get("/sections/{section_id}", response_model=SectionResponse)
        async def get_section(section_id: str):
            """Get a section by ID."""
            try:
                with self._lock:
                    section = self._section_repo.find_by_id(section_id)
                    
                    if not section:
                        raise HTTPException(status_code=404, detail="Section not found")
                    
                    return self._section_to_response(section)
            
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
        
        # Enrollment endpoints
        @self.app.post("/enrollments", response_model=EnrollmentResponse)
        async def enroll_student(enrollment_data: EnrollmentRequest):
            """Enroll a student in a section."""
            try:
                with self._lock:
                    # Get student and section
                    student = self._student_repo.find_by_student_id(enrollment_data.student_id)
                    section = self._section_repo.find_by_id(enrollment_data.section_id)
                    
                    if not student:
                        raise HTTPException(status_code=404, detail="Student not found")
                    
                    if not section:
                        raise HTTPException(status_code=404, detail="Section not found")
                    
                    # Enroll student
                    result = self._enrollment_service.enroll_student(student, section)
                    
                    return EnrollmentResponse(
                        success=result.success,
                        message=result.message,
                        status=result.status.value,
                        waitlist_position=result.waitlist_position
                    )
            
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
        
        @self.app.get("/students/{student_id}/enrollments", response_model=List[str])
        async def get_student_enrollments(student_id: str):
            """Get student enrollments."""
            try:
                with self._lock:
                    enrollments = self._enrollment_service.get_enrollments(student_id)
                    return enrollments
            
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
        
        # Scheduling endpoints
        @self.app.post("/schedules", response_model=ScheduleResponse)
        async def schedule_section(schedule_data: ScheduleRequest):
            """Schedule a section."""
            try:
                with self._lock:
                    # Convert time slots
                    time_slots = []
                    for slot_data in schedule_data.time_slots:
                        time_slot = {
                            'start_time': datetime.fromisoformat(slot_data['start_time']),
                            'end_time': datetime.fromisoformat(slot_data['end_time']),
                            'day_of_week': slot_data['day_of_week']
                        }
                        time_slots.append(time_slot)
                    
                    # Create schedule request
                    from ..services.scheduler_service import ScheduleRequest as SchedulerRequest
                    schedule_request = SchedulerRequest(
                        section_id=schedule_data.section_id,
                        time_slots=time_slots,
                        room_requirements=schedule_data.room_requirements,
                        constraints=schedule_data.constraints
                    )
                    
                    # Schedule section
                    result = self._scheduler_service.schedule_section(schedule_request)
                    
                    return ScheduleResponse(
                        success=result.success,
                        message=result.message,
                        schedule_id=result.schedule_id,
                        assigned_room=result.assigned_room,
                        assigned_times=result.assigned_times,
                        conflicts=result.conflicts
                    )
            
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
        
        # ML endpoints
        @self.app.post("/ml/predict", response_model=MLPredictionResponse)
        async def get_ml_prediction(prediction_data: MLPredictionRequest):
            """Get ML prediction."""
            try:
                with self._lock:
                    # This would integrate with ML services
                    # For now, return a mock response
                    prediction = {"prediction": "mock_prediction", "confidence": 0.85}
                    explanation = {"explanation": "mock_explanation"}
                    
                    return MLPredictionResponse(
                        success=True,
                        message="Prediction generated successfully",
                        prediction=prediction,
                        explanation=explanation
                    )
            
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
        
        # Statistics endpoints
        @self.app.get("/statistics", response_model=StatisticsResponse)
        async def get_statistics():
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
                    
                    return StatisticsResponse(
                        success=True,
                        message="Statistics retrieved successfully",
                        statistics=statistics
                    )
            
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
    
    def _student_to_response(self, student: Student) -> StudentResponse:
        """Convert Student entity to response model."""
        return StudentResponse(
            id=student.id,
            first_name=student.first_name,
            last_name=student.last_name,
            email=student.email,
            student_id=student.student_id,
            grade_level=student.grade_level.value,
            gpa=student.gpa,
            academic_standing=student.academic_standing,
            advisor=student.advisor,
            enrollments=list(student.enrollments),
            created_at=student.created_at,
            updated_at=student.updated_at,
            version=student.version,
            status=student.status.value
        )
    
    def _course_to_response(self, course: Course) -> CourseResponse:
        """Convert Course entity to response model."""
        return CourseResponse(
            id=course.id,
            course_code=course.course_code,
            title=course.title,
            description=course.description,
            credits=course.credits,
            department=course.department,
            prerequisites=list(course.prerequisites),
            sections=list(course.sections),
            syllabus=course.syllabus,
            created_at=course.created_at,
            updated_at=course.updated_at,
            version=course.version,
            status=course.status.value
        )
    
    def _section_to_response(self, section: Section) -> SectionResponse:
        """Convert Section entity to response model."""
        return SectionResponse(
            id=section.id,
            course_id=section.course_id,
            section_number=section.section_number,
            semester=section.semester,
            year=section.year,
            instructor_id=section.instructor_id,
            room_id=section.room_id,
            schedule=section.schedule,
            capacity=section.capacity,
            enrolled_count=section.enrolled_count,
            waitlist_count=section.waitlist_count,
            is_full=section.is_full,
            created_at=section.created_at,
            updated_at=section.updated_at,
            version=section.version,
            status=section.status.value
        )
