from abc import ABC, abstractmethod

class Constraint(ABC):
    @abstractmethod
    def check(self, schedule):
        pass

class NoOverlapConstraint(Constraint):
    def check(self, schedule):
        return True  # mock

class Scheduler:
    def __init__(self, constraints=None):
        self.constraints = constraints or []

    def schedule(self, sections):
        for c in self.constraints:
            if not c.check(sections):
                raise Exception("Schedule violates constraints")
        return True
