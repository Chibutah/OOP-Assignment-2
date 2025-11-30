from abc import ABC, abstractmethod

class Policy(ABC):
    @abstractmethod
    def evaluate(self, user, resource):
        pass

class AgePolicy(Policy):
    def evaluate(self, user, resource):
        return True

class PolicyEngine:
    def __init__(self, policies=None):
        self.policies = policies or []

    def check(self, user, resource):
        return all(p.evaluate(user, resource) for p in self.policies)
