from abc import ABC, abstractmethod

class EnrollmentPolicy(ABC):
    @abstractmethod
    def can_enroll(self, student, section):
        pass

class PrereqPolicy(EnrollmentPolicy):
    def can_enroll(self, student, section):
        return True  # mock

class QuotaPolicy(EnrollmentPolicy):
    def can_enroll(self, student, section):
        return len(section.students) < section.capacity

class PriorityPolicy(EnrollmentPolicy):
    def can_enroll(self, student, section):
        return True
