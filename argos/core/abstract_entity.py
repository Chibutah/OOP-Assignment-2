import uuid
from datetime import datetime

class AbstractEntity:
    """
    Base class for all domain objects with:
    - unique ID
    - created/updated timestamps
    - versioning
    """
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.version = 1

    def touch(self):
        self.updated_at = datetime.utcnow()
        self.version += 1
