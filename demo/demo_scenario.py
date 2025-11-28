#!/usr/bin/env python3
"""
Demo scenario for the Argos platform.
"""

import sys
import os
import time
import json
from datetime import datetime, timezone

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from argos.main import ArgosPlatform
from argos.core.entities import Student, Course, Section, Room, Facility
from argos.core.enums import PersonType, GradeLevel


def run_demo():
    """Run a comprehensive demo of the Argos platform."""
    print("=" * 60)
    print("ARGOS CAMPUS MANAGEMENT PLATFORM - DEMO")
    print("=" * 60)
    
    # Initialize platform
    config = {
        'database_type': 'sqlite',
        'database_config': {'database_path': 'demo_argos.db'},
        'event_store_type': 'file',
        'event_store_config': {'base_path': 'demo_events'},
        'max_workers': 5,
        'node_id': 'demo-node-1'
    }
    
    platform = ArgosPlatform(config)
    
    try:
        # Create sample data
        print("\n1. Creating sample data...")
        create_sample_data(platform)
        
        # Demonstrate enrollment
        print("\n2. Demonstrating enrollment system...")
        demonstrate_enrollment(platform)
        
        # Demonstrate scheduling
        print("\n3. Demonstrating scheduling system...")
        demonstrate_scheduling(platform)
        
        # Demonstrate concurrency
        print("\n4. Demonstrating concurrency control...")
        demonstrate_concurrency(platform)
        
        # Demonstrate event sourcing
        print("\n5. Demonstrating event sourcing...")
        demonstrate_event_sourcing(platform)
        
        # Show statistics
        print("\n6. Platform statistics...")
        show_statistics(platform)
        
        print("\n" + "=" * 60)
        print("DEMO COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nDemo failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        platform.stop_platform()


def create_sample_data(platform):
    """Create comprehensive sample data."""
    print("  Creating facilities and rooms...")
    
    # Create facilities
    facilities = [
        Facility("Computer Science Building", "academic", "Main Campus"),
        Facility("Mathematics Building", "academic", "Main Campus"),
        Facility("Library", "library", "Central Campus"),
        Facility("Student Center", "student", "Central Campus")
    ]
    
    for facility in facilities:
        platform._repositories['facility'].save(facility)
    
    # Create rooms
    rooms = [
        Room("CS101", facilities[0].id, "lecture", 50),
        Room("CS102", facilities[0].id, "lecture", 30),
        Room("CS201", facilities[0].id, "lab", 25),
        Room("MATH101", facilities[1].id, "lecture", 40),
        Room("LIB001", facilities[2].id, "study", 100),
    ]
    
    for room in rooms:
        room.add_equipment("projector")
        room.add_equipment("whiteboard")
        if "lab" in room.room_type:
            room.add_equipment("computers")
        platform._repositories['room'].save(room)
    
    print("  Creating courses...")
    
    # Create courses
    courses = [
        Course("CS101", "Introduction to Computer Science", 
               "Basic concepts of computer science and programming", 3, "Computer Science"),
        Course("CS201", "Data Structures and Algorithms", 
               "Advanced programming concepts and data structures", 3, "Computer Science"),
        Course("CS301", "Software Engineering", 
               "Software development methodologies and practices", 3, "Computer Science"),
        Course("MATH101", "Calculus I", 
               "Differential and integral calculus", 4, "Mathematics"),
        Course("MATH201", "Linear Algebra", 
               "Vector spaces and linear transformations", 3, "Mathematics"),
    ]
    
    for course in courses:
        platform._repositories['course'].save(course)
    
    # Add prerequisites
    cs201 = platform._repositories['course'].find_by_course_code("CS201")
    cs301 = platform._repositories['course'].find_by_course_code("CS301")
    if cs201 and cs301:
        cs301.add_prerequisite(cs201.id)
        platform._repositories['course'].save(cs301)
    
    print("  Creating sections...")
    
    # Create sections
    sections = [
        Section(courses[0].id, "001", "Fall", 2024, "instructor-1"),
        Section(courses[0].id, "002", "Fall", 2024, "instructor-2"),
        Section(courses[1].id, "001", "Fall", 2024, "instructor-3"),
        Section(courses[2].id, "001", "Spring", 2025, "instructor-4"),
        Section(courses[3].id, "001", "Fall", 2024, "instructor-5"),
    ]
    
    for i, section in enumerate(sections):
        section.set_capacity(30 + i * 5)
        if i < len(rooms):
            section.set_room(rooms[i].id)
        platform._repositories['section'].save(section)
    
    print("  Creating students...")
    
    # Create students
    students = [
        Student("Alice", "Johnson", "alice@university.edu", "S001", GradeLevel.FRESHMAN),
        Student("Bob", "Smith", "bob@university.edu", "S002", GradeLevel.SOPHOMORE),
        Student("Carol", "Davis", "carol@university.edu", "S003", GradeLevel.JUNIOR),
        Student("David", "Wilson", "david@university.edu", "S004", GradeLevel.SENIOR),
        Student("Eve", "Brown", "eve@university.edu", "S005", GradeLevel.GRADUATE),
    ]
    
    for student in students:
        # Set some GPAs
        if student.student_id == "S002":
            student.update_gpa(3.8)
        elif student.student_id == "S003":
            student.update_gpa(3.5)
        elif student.student_id == "S004":
            student.update_gpa(3.2)
        
        platform._repositories['student'].save(student)
    
    print("  ✓ Sample data created successfully")


def demonstrate_enrollment(platform):
    """Demonstrate the enrollment system."""
    students = platform._repositories['student'].find_all()
    sections = platform._repositories['section'].find_all()
    
    if not students or not sections:
        print("  No students or sections available for enrollment demo")
        return
    
    print(f"  Enrolling {len(students)} students in sections...")
    
    # Enroll students in sections
    for i, student in enumerate(students):
        section = sections[i % len(sections)]
        result = platform._enrollment_service.enroll_student(student, section)
        print(f"    {student.student_id} -> {section.section_number}: {result.status.value}")
    
    # Try to over-enroll a section
    print("  Testing over-enrollment (waitlist)...")
    full_section = sections[0]
    for i in range(5):  # Try to enroll 5 more students
        student = students[i % len(students)]
        result = platform._enrollment_service.enroll_student(student, full_section)
        print(f"    {student.student_id} -> {full_section.section_number}: {result.status.value}")
    
    # Show enrollment statistics
    stats = platform._enrollment_service.get_statistics()
    print(f"  Enrollment statistics: {stats}")


def demonstrate_scheduling(platform):
    """Demonstrate the scheduling system."""
    sections = platform._repositories['section'].find_all()
    rooms = platform._repositories['room'].find_all()
    
    if not sections or not rooms:
        print("  No sections or rooms available for scheduling demo")
        return
    
    print("  Scheduling sections...")
    
    from argos.services.scheduler_service import ScheduleRequest, TimeSlot
    from datetime import datetime, timedelta
    
    # Schedule a section
    section = sections[0]
    start_time = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(hours=1)
    
    time_slots = [TimeSlot(
        start_time=start_time,
        end_time=end_time,
        day_of_week=1  # Monday
    )]
    
    room_requirements = {
        'min_capacity': 30,
        'room_type': 'lecture',
        'equipment': ['projector', 'whiteboard'],
        'access_control': False
    }
    
    schedule_request = ScheduleRequest(
        section_id=section.id,
        time_slots=time_slots,
        room_requirements=room_requirements
    )
    
    result = platform._scheduler_service.schedule_section(schedule_request)
    print(f"    Section {section.section_number}: {result.message}")
    if result.success:
        print(f"      Assigned room: {result.assigned_room}")
    
    # Show scheduling statistics
    stats = platform._scheduler_service.get_statistics()
    print(f"  Scheduling statistics: {stats}")


def demonstrate_concurrency(platform):
    """Demonstrate concurrency control."""
    print("  Running concurrency stress test...")
    
    from argos.services.concurrency_manager import ConcurrencyStressTest
    
    stress_test = ConcurrencyStressTest(platform._concurrency_manager)
    results = stress_test.run_test(num_clients=50, operations_per_client=20)
    
    print(f"    Successful operations: {results['successful_operations']}")
    print(f"    Failed operations: {results['failed_operations']}")
    print(f"    Operations per second: {results['operations_per_second']:.2f}")
    print(f"    Total time: {results['total_time']:.2f}s")


def demonstrate_event_sourcing(platform):
    """Demonstrate event sourcing."""
    print("  Publishing events...")
    
    from argos.core.entities import Event
    from argos.core.enums import EventType
    
    # Create some events
    events = [
        Event(EventType.ENROLLMENT, "student-S001", {
            'student_id': 'S001',
            'section_id': 'section-1',
            'action': 'enrolled'
        }),
        Event(EventType.SYSTEM_ALERT, "system", {
            'alert_type': 'high_cpu_usage',
            'severity': 'warning'
        }),
        Event(EventType.POLICY_CHANGE, "policy", {
            'policy_id': 'enrollment-policy-1',
            'action': 'updated'
        })
    ]
    
    for event in events:
        platform._event_service.publish_event(event)
    
    # Show event statistics
    stats = platform._event_service.get_processing_statistics()
    print(f"  Event processing statistics: {stats}")


def show_statistics(platform):
    """Show platform statistics."""
    print("  Gathering platform statistics...")
    
    # Enrollment statistics
    enrollment_stats = platform._enrollment_service.get_statistics()
    print(f"    Enrollment Service:")
    print(f"      Total enrollments: {enrollment_stats['total_enrollments']}")
    print(f"      Total waitlisted: {enrollment_stats['total_waitlisted']}")
    print(f"      Active policies: {enrollment_stats['active_policies']}")
    
    # Scheduler statistics
    scheduler_stats = platform._scheduler_service.get_statistics()
    print(f"    Scheduler Service:")
    print(f"      Total schedules: {scheduler_stats['total_schedules']}")
    print(f"      Active schedules: {scheduler_stats['active_schedules']}")
    print(f"      Total rooms: {scheduler_stats['total_rooms']}")
    
    # Event service statistics
    event_stats = platform._event_service.get_processing_statistics()
    print(f"    Event Service:")
    print(f"      Total processed: {event_stats['total_processed']}")
    print(f"      Success rate: {event_stats['success_rate']:.2%}")
    print(f"      Queue size: {event_stats['queue_size']}")
    
    # Database statistics
    student_count = platform._repositories['student'].count()
    course_count = platform._repositories['course'].count()
    section_count = platform._repositories['section'].count()
    room_count = platform._repositories['room'].count()
    
    print(f"    Database:")
    print(f"      Students: {student_count}")
    print(f"      Courses: {course_count}")
    print(f"      Sections: {section_count}")
    print(f"      Rooms: {room_count}")


if __name__ == "__main__":
    run_demo()
