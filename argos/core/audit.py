import hashlib
import json
from .abstract_entity import AbstractEntity

class AuditLogEntry(AbstractEntity):
    def __init__(self, action, data, prev_hash):
        super().__init__()
        self.action = action
        self.data = data
        self.prev_hash = prev_hash
        self.hash = self._compute_hash()

    def _compute_hash(self):
        h = hashlib.sha256()
        h.update(json.dumps({
            "action": self.action,
            "data": self.data,
            "prev_hash": self.prev_hash
        }).encode())
        return h.hexdigest()
