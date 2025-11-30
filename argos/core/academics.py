from .abstract_entity import AbstractEntity

class Course(AbstractEntity):
    def __init__(self, code, name):
        super().__init__()
        self.code = code
        self.name = name
        self.sections = []

class Section(AbstractEntity):
    def __init__(self, course_id, capacity):
        super().__init__()
        self.course_id = course_id
        self.capacity = capacity
        self.students = []

class Syllabus(AbstractEntity):
    def __init__(self, course_id, topics):
        super().__init__()
        self.course_id = course_id
        self.topics = topics

class Assessment(AbstractEntity):
    def __init__(self, section_id, title, max_points):
        super().__init__()
        self.section_id = section_id
        self.title = title
        self.max_points = max_points

class Grade:
    """Immutable value object."""
    def __init__(self, assessment_id, student_id, value):
        self.assessment_id = assessment_id
        self.student_id = student_id
        self.value = value
