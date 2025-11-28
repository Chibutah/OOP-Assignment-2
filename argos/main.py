"""
Main entry point for the Argos platform.
"""

import asyncio
import threading
import time
from typing import Optional

import grpc
from concurrent import futures

from .core.entities import Student, Course, Section, Room, Facility
from .core.enums import PersonType, GradeLevel
from .persistence import DatabaseFactory, EventStoreFactory, MigrationManager
from .persistence.repositories import (
    StudentRepository, CourseRepository, SectionRepository, 
    GradeRepository, FacilityRepository, RoomRepository
)
from .services import (
    ConcurrencyManager, EnrollmentService, SchedulerService, 
    EventService, DistributedCoordinator
)
from .api.grpc_api import ArgosGrpcService
from .api.rest_api import ArgosRestAPI


class ArgosPlatform:
    """Main platform class that orchestrates all services."""
    
    def __init__(self, config: Optional[dict] = None):
        self._config = config or {}
        self._database = None
        self._event_store = None
        self._migration_manager = None
        self._concurrency_manager = None
        self._enrollment_service = None
        self._scheduler_service = None
        self._event_service = None
        self._distributed_coordinator = None
        self._grpc_server = None
        self._rest_app = None
        self._running = False
        
        # Initialize platform
        self._initialize_platform()
    
    def _initialize_platform(self):
        """Initialize the platform with all services."""
        print("Initializing Argos platform...")
        
        # Initialize database
        db_type = self._config.get('database_type', 'sqlite')
        db_config = self._config.get('database_config', {})
        self._database = DatabaseFactory.create_database(db_type, **db_config)
        print(f"✓ Database initialized: {db_type}")
        
        # Initialize event store
        event_store_type = self._config.get('event_store_type', 'file')
        event_store_config = self._config.get('event_store_config', {})
        self._event_store = EventStoreFactory.create_event_store(event_store_type, **event_store_config)
        print(f"✓ Event store initialized: {event_store_type}")
        
        # Initialize migration manager (skip for now)
        # self._migration_manager = MigrationManager(self._database)
        # self._migration_manager.create_initial_migrations()
        # self._migration_manager.migrate_up()
        print("✓ Database migrations skipped for demo")
        
        # Initialize concurrency manager
        self._concurrency_manager = ConcurrencyManager(
            max_workers=self._config.get('max_workers', 10)
        )
        print("✓ Concurrency manager initialized")
        
        # Initialize repositories
        self._repositories = {
            'student': StudentRepository(self._database),
            'course': CourseRepository(self._database),
            'section': SectionRepository(self._database),
            'grade': GradeRepository(self._database),
            'facility': FacilityRepository(self._database),
            'room': RoomRepository(self._database)
        }
        print("✓ Repositories initialized")
        
        # Initialize services
        self._enrollment_service = EnrollmentService(self._concurrency_manager)
        self._scheduler_service = SchedulerService(self._concurrency_manager)
        self._event_service = EventService(self._concurrency_manager)
        self._distributed_coordinator = DistributedCoordinator(
            node_id=self._config.get('node_id', 'argos-node-1'),
            concurrency_manager=self._concurrency_manager
        )
        print("✓ Services initialized")
        
        # Initialize APIs
        self._grpc_service = ArgosGrpcService(
            self._database,
            self._enrollment_service,
            self._scheduler_service,
            self._event_service
        )
        
        self._rest_app = ArgosRestAPI(
            self._database,
            self._enrollment_service,
            self._scheduler_service,
            self._event_service
        )
        print("✓ APIs initialized")
        
        print("✓ Argos platform initialized successfully!")
    
    def start_grpc_server(self, port: int = 50051, max_workers: int = 10):
        """Start the gRPC server."""
        if self._grpc_server:
            print("gRPC server already running")
            return
        
        self._grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
        
        # Add service to server
        from .api import argos_pb2_grpc
        argos_pb2_grpc.add_ArgosServiceServicer_to_server(self._grpc_service, self._grpc_server)
        
        # Start server
        listen_addr = f'[::]:{port}'
        self._grpc_server.add_insecure_port(listen_addr)
        self._grpc_server.start()
        
        print(f"✓ gRPC server started on port {port}")
    
    def start_rest_server(self, host: str = "0.0.0.0", port: int = 8000):
        """Start the REST server."""
        if self._rest_app is None:
            print("REST app not initialized")
            return
        
        import uvicorn
        
        def run_server():
            uvicorn.run(
                self._rest_app.app,
                host=host,
                port=port,
                log_level="info"
            )
        
        # Start server in a separate thread
        self._rest_thread = threading.Thread(target=run_server, daemon=True)
        self._rest_thread.start()
        
        print(f"✓ REST server started on {host}:{port}")
    
    def start_platform(self, grpc_port: int = 50051, rest_port: int = 8000):
        """Start the entire platform."""
        if self._running:
            print("Platform already running")
            return
        
        print("Starting Argos platform...")
        
        # Start gRPC server
        self.start_grpc_server(grpc_port)
        
        # Start REST server
        self.start_rest_server(port=rest_port)
        
        self._running = True
        print(f"✓ Argos platform started successfully!")
        print(f"  - gRPC API: localhost:{grpc_port}")
        print(f"  - REST API: http://localhost:{rest_port}")
        print(f"  - API Docs: http://localhost:{rest_port}/docs")
    
    def stop_platform(self):
        """Stop the platform."""
        if not self._running:
            print("Platform not running")
            return
        
        print("Stopping Argos platform...")
        
        # Stop gRPC server
        if self._grpc_server:
            self._grpc_server.stop(grace=5.0)
            self._grpc_server = None
            print("✓ gRPC server stopped")
        
        # Cleanup concurrency manager
        if self._concurrency_manager:
            self._concurrency_manager.cleanup()
            print("✓ Concurrency manager cleaned up")
        
        self._running = False
        print("✓ Argos platform stopped")
    
    def create_sample_data(self):
        """Create sample data for demonstration."""
        print("Creating sample data...")
        
        # Create sample facilities and rooms
        facility = Facility(
            name="Computer Science Building",
            facility_type="academic",
            location="Main Campus"
        )
        self._repositories['facility'].save(facility)
        
        room = Room(
            room_number="CS101",
            facility_id=facility.id,
            room_type="lecture",
            capacity=50
        )
        room.add_equipment("projector")
        room.add_equipment("whiteboard")
        self._repositories['room'].save(room)
        
        # Create sample course
        course = Course(
            course_code="CS101",
            title="Introduction to Computer Science",
            description="Basic concepts of computer science and programming",
            credits=3,
            department="Computer Science"
        )
        self._repositories['course'].save(course)
        
        # Create sample section
        section = Section(
            course_id=course.id,
            section_number="001",
            semester="Fall",
            year=2024,
            instructor_id="instructor-1"
        )
        section.set_capacity(30)
        section.set_room(room.id)
        self._repositories['section'].save(section)
        
        # Create sample students
        students = [
            Student("Alice", "Johnson", "alice@university.edu", "S001", GradeLevel.FRESHMAN),
            Student("Bob", "Smith", "bob@university.edu", "S002", GradeLevel.SOPHOMORE),
            Student("Carol", "Davis", "carol@university.edu", "S003", GradeLevel.JUNIOR),
        ]
        
        for student in students:
            self._repositories['student'].save(student)
        
        print("✓ Sample data created")
    
    def run_demo(self):
        """Run a demonstration of the platform."""
        print("Running Argos platform demonstration...")
        
        # Create sample data
        self.create_sample_data()
        
        # Get some statistics
        enrollment_stats = self._enrollment_service.get_statistics()
        scheduler_stats = self._scheduler_service.get_statistics()
        event_stats = self._event_service.get_processing_statistics()
        
        print("\n=== Platform Statistics ===")
        print(f"Enrollment Service: {enrollment_stats}")
        print(f"Scheduler Service: {scheduler_stats}")
        print(f"Event Service: {event_stats}")
        
        # Demonstrate enrollment
        students = self._repositories['student'].find_all()
        sections = self._repositories['section'].find_all()
        
        if students and sections:
            print(f"\n=== Enrollment Demo ===")
            student = students[0]
            section = sections[0]
            
            print(f"Enrolling student {student.student_id} in section {section.section_number}")
            result = self._enrollment_service.enroll_student(student, section)
            print(f"Result: {result}")
        
        print("\n✓ Demo completed")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Argos Campus Management Platform")
    parser.add_argument("--grpc-port", type=int, default=50051, help="gRPC server port")
    parser.add_argument("--rest-port", type=int, default=8000, help="REST server port")
    parser.add_argument("--demo", action="store_true", help="Run demo mode")
    parser.add_argument("--config", type=str, help="Configuration file path")
    
    args = parser.parse_args()
    
    # Load configuration
    config = {}
    if args.config:
        import json
        with open(args.config, 'r') as f:
            config = json.load(f)
    
    # Create and start platform
    platform = ArgosPlatform(config)
    
    try:
        if args.demo:
            platform.run_demo()
        else:
            platform.start_platform(args.grpc_port, args.rest_port)
            
            # Keep running
            print("\nPlatform is running. Press Ctrl+C to stop.")
            while True:
                time.sleep(1)
    
    except KeyboardInterrupt:
        print("\nShutting down...")
        platform.stop_platform()


if __name__ == "__main__":
    main()
