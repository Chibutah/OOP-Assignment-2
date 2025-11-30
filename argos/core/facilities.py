from .abstract_entity import AbstractEntity

class Facility(AbstractEntity):
    def __init__(self, name):
        super().__init__()
        self.name = name

class Room(Facility):
    def __init__(self, name, capacity):
        super().__init__(name)
        self.capacity = capacity
        self.resources = []

class Resource(AbstractEntity):
    def __init__(self, type, status="active"):
        super().__init__()
        self.type = type
        self.status = status
