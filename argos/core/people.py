from .abstract_entity import AbstractEntity

class Person(AbstractEntity):
    def __init__(self, name, email):
        super().__init__()
        self.name = name
        self.email = email
        self.roles = set()

    def add_role(self, role):
        self.roles.add(role)

    def remove_role(self, role):
        self.roles.discard(role)

class Student(Person):
    pass

class Lecturer(Person):
    pass

class Staff(Person):
    pass

class Guest(Person):
    pass
