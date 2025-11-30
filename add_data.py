
"""
Script to add sample data to the Argos platform via REST API.
Make sure the server is running before executing this script.

Usage:
    python add_data.py
"""

import requests
import json
import sys
import os


def _console_supports_utf8() -> bool:
    try:
        enc = getattr(sys.stdout, "encoding", None)
        return enc is not None and "utf" in enc.lower()
    except Exception:
        return False


_OK_CHAR = "\u2713" if _console_supports_utf8() else "[OK]"
_FAIL_CHAR = "\u2717" if _console_supports_utf8() else "[FAIL]"
_WARN_CHAR = "\u26A0" if _console_supports_utf8() else "[WARN]"
_INFO_CHAR = "\u2139" if _console_supports_utf8() else "[INFO]"


def _detect_base_url() -> str:
    """Determine a reachable BASE_URL.

    Priority: environment variable `ARGOS_BASE_URL`, then common local ports.
    If nothing responds, fall back to http://127.0.0.1:8000.
    """
    env = os.environ.get("ARGOS_BASE_URL")
    if env:
        return env

    candidates = [
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8888",
        "http://localhost:8000",
        "http://localhost:8888",
    ]

    for c in candidates:
        try:
            resp = requests.get(f"{c}/health", timeout=0.5)
            if resp.status_code == 200:
                return c
        except Exception:
            continue

    return candidates[0]


BASE_URL = _detect_base_url()

def check_server():
    """Check if the server is running."""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=2)
        if response.status_code == 200:
            print(f"{_OK_CHAR} Server is running")
            return True
    except requests.exceptions.RequestException:
        print(f"{_FAIL_CHAR} Server is not running!")
        print("\nPlease start the server first:")
        print("  source venv_new/bin/activate")
        print("  python -m argos.main --grpc-port 50052 --rest-port 8888")
        return False

def create_student(first_name, last_name, email, student_id, grade_level):
    """Create a new student."""
    url = f"{BASE_URL}/students"
    data = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "student_id": student_id,
        "grade_level": grade_level
    }
    try:
        response = requests.post(url, json=data)
        if response.status_code == 201:
            print(f"{_OK_CHAR} Created student: {first_name} {last_name} ({student_id})")
            return response.json()
        else:
            print(f"{_FAIL_CHAR} Failed to create student: {response.text}")
            return None
    except Exception as e:
        print(f"{_FAIL_CHAR} Error creating student: {e}")
        return None

def create_course(course_code, title, description, credits, department, prerequisites=None):
    """Create a new course."""
    url = f"{BASE_URL}/courses"
    data = {
        "course_code": course_code,
        "title": title,
        "description": description,
        "credits": credits,
        "department": department,
        "prerequisites": prerequisites or []
    }
    try:
        response = requests.post(url, json=data)
        if response.status_code == 201:
            print(f"{_OK_CHAR} Created course: {course_code} - {title}")
            return response.json()
        else:
            print(f"{_FAIL_CHAR} Failed to create course: {response.text}")
            return None
    except Exception as e:
        print(f"{_FAIL_CHAR} Error creating course: {e}")
        return None

def create_section(course_id, section_number, semester, year, instructor_id, capacity):
    """Create a new section."""
    url = f"{BASE_URL}/sections"
    data = {
        "course_id": course_id,
        "section_number": section_number,
        "semester": semester,
        "year": year,
        "instructor_id": instructor_id,
        "capacity": capacity
    }
    try:
        response = requests.post(url, json=data)
        if response.status_code == 201:
            print(f"{_OK_CHAR} Created section: {section_number} for course {course_id}")
            return response.json()
        else:
            print(f"{_FAIL_CHAR} Failed to create section: {response.text}")
            return None
    except Exception as e:
        print(f"{_FAIL_CHAR} Error creating section: {e}")
        return None

def enroll_student(student_id, section_id):
    """Enroll a student in a section."""
    url = f"{BASE_URL}/enrollments"
    data = {
        "student_id": student_id,
        "section_id": section_id
    }
    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            result = response.json()
            status = result.get('status', 'unknown')
            if status == 'confirmed':
                print(f"{_OK_CHAR} Enrolled student {student_id}: {result['message']}")
            elif status == 'waitlisted':
                pos = result.get('waitlist_position', '?')
                print(f"{_WARN_CHAR} Student {student_id} waitlisted at position {pos}")
            else:
                print(f"{_INFO_CHAR} Student {student_id}: {result['message']}")
            return result
        else:
            print(f"{_FAIL_CHAR} Failed to enroll student: {response.text}")
            return None
    except Exception as e:
        print(f"{_FAIL_CHAR} Error enrolling student: {e}")
        return None

def list_students():
    """List all students."""
    url = f"{BASE_URL}/students"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            students = response.json()
            print(f"\n{'='*60}")
            print(f"Students ({len(students)})")
            print(f"{'='*60}")
            for student in students:
                print(f"  {student['student_id']:8} | {student['first_name']} {student['last_name']:15} | {student['grade_level']:12} | {student['email']}")
            return students
        else:
            print(f"{_FAIL_CHAR} Failed to list students: {response.text}")
            return []
    except Exception as e:
        print(f"{_FAIL_CHAR} Error listing students: {e}")
        return []

def list_courses():
    """List all courses."""
    url = f"{BASE_URL}/courses"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            courses = response.json()
            print(f"\n{'='*60}")
            print(f"Courses ({len(courses)})")
            print(f"{'='*60}")
            for course in courses:
                prereqs = ", ".join(course.get('prerequisites', [])) or "None"
                print(f"  {course['course_code']:10} | {course['title']:30} | {course['credits']} credits | Prereqs: {prereqs}")
            return courses
        else:
            print(f"{_FAIL_CHAR} Failed to list courses: {response.text}")
            return []
    except Exception as e:
        print(f"{_FAIL_CHAR} Error listing courses: {e}")
        return []

def get_statistics():
    """Get system statistics."""
    url = f"{BASE_URL}/statistics"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            stats = response.json()
            print(f"\n{'='*60}")
            print("System Statistics")
            print(f"{'='*60}")
            print(json.dumps(stats['statistics'], indent=2))
            return stats
        else:
            print(f"{_FAIL_CHAR} Failed to get statistics: {response.text}")
            return None
    except Exception as e:
        print(f"{_FAIL_CHAR} Error getting statistics: {e}")
        return None

def main():
    """Main execution."""
    print("="*60)
    print("Argos Platform - Data Addition Script")
    print("="*60)
    print()
    
    # Check if server is running
    if not check_server():
        sys.exit(1)
    
    print("\n" + "="*60)
    print("Adding Sample Data...")
    print("="*60 + "\n")
    
    # Create students
    print("Creating students...")
    students = []
    students.append(create_student("Alice", "Johnson", "alice.johnson@university.edu", "S001", "freshman"))
    students.append(create_student("Bob", "Smith", "bob.smith@university.edu", "S002", "sophomore"))
    students.append(create_student("Carol", "Davis", "carol.davis@university.edu", "S003", "junior"))
    students.append(create_student("David", "Wilson", "david.wilson@university.edu", "S004", "senior"))
    students.append(create_student("Emma", "Brown", "emma.brown@university.edu", "S005", "freshman"))
    students.append(create_student("Frank", "Miller", "frank.miller@university.edu", "S006", "sophomore"))
    
    # Create courses
    print("\nCreating courses...")
    courses = []
    courses.append(create_course("CS101", "Introduction to Programming", "Learn Python programming basics", 3, "Computer Science"))
    courses.append(create_course("CS201", "Data Structures", "Advanced data structures and algorithms", 4, "Computer Science", ["CS101"]))
    courses.append(create_course("CS301", "Database Systems", "Relational databases and SQL", 3, "Computer Science", ["CS201"]))
    courses.append(create_course("MATH101", "Calculus I", "Differential calculus", 4, "Mathematics"))
    courses.append(create_course("MATH201", "Calculus II", "Integral calculus", 4, "Mathematics", ["MATH101"]))
    courses.append(create_course("ENG101", "English Composition", "Academic writing skills", 3, "English"))
    
    # Create sections
    print("\nCreating sections...")
    sections = []
    if courses[0]:  # CS101
        sections.append(create_section(courses[0]['id'], "001", "Fall", 2024, "instructor-1", 30))
        sections.append(create_section(courses[0]['id'], "002", "Fall", 2024, "instructor-2", 25))
    
    if courses[1]:  # CS201
        sections.append(create_section(courses[1]['id'], "001", "Fall", 2024, "instructor-1", 20))
    
    if courses[3]:  # MATH101
        sections.append(create_section(courses[3]['id'], "001", "Fall", 2024, "instructor-3", 35))
    
    if courses[5]:  # ENG101
        sections.append(create_section(courses[5]['id'], "001", "Fall", 2024, "instructor-4", 25))
    
    # Enroll students
    print("\nEnrolling students...")
    if students[0] and sections[0]:  # Alice in CS101-001
        enroll_student(students[0]['student_id'], sections[0]['id'])
    
    if students[1] and sections[0]:  # Bob in CS101-001
        enroll_student(students[1]['student_id'], sections[0]['id'])
    
    if students[2] and sections[1]:  # Carol in CS101-002
        enroll_student(students[2]['student_id'], sections[1]['id'])
    
    if students[3] and sections[2]:  # David in CS201-001
        enroll_student(students[3]['student_id'], sections[2]['id'])
    
    if students[4] and sections[3]:  # Emma in MATH101-001
        enroll_student(students[4]['student_id'], sections[3]['id'])
    
    if students[5] and sections[4]:  # Frank in ENG101-001
        enroll_student(students[5]['student_id'], sections[4]['id'])
    
    # Also enroll some students in multiple courses
    if students[0] and sections[3]:  # Alice in MATH101
        enroll_student(students[0]['student_id'], sections[3]['id'])
    
    if students[1] and sections[4]:  # Bob in ENG101
        enroll_student(students[1]['student_id'], sections[4]['id'])
    
    # Display results
    list_students()
    list_courses()
    get_statistics()
    
    print("\n" + "="*60)
    print(f"{_OK_CHAR} Sample data added successfully!")
    print("="*60)
    print("\nYou can now:")
    print(f"  - View API docs: {BASE_URL}/docs")
    print(f"  - List students: curl {BASE_URL}/students")
    print(f"  - List courses: curl {BASE_URL}/courses")
    print(f"  - Get statistics: curl {BASE_URL}/statistics")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{_FAIL_CHAR} Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n{_FAIL_CHAR} Unexpected error: {e}")
        sys.exit(1)
