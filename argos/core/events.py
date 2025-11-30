from datetime import datetime
from .abstract_entity import AbstractEntity

class Event(AbstractEntity):
    def __init__(self, type, data):
        super().__init__()
        self.type = type
        self.data = data
        self.timestamp = datetime.utcnow()

class EventStream:
    def __init__(self):
        self.events = []

    def publish(self, event):
        self.events.append(event)

    def replay(self):
        for event in self.events:
            yield event
