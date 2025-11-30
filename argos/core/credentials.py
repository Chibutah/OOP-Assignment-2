from abc import ABC, abstractmethod
from .abstract_entity import AbstractEntity

class Credential(ABC):
    """Strategy interface."""
    @abstractmethod
    def authenticate(self):
        pass

class PasswordCredential(Credential):
    def __init__(self, username, password):
        self.username = username
        self.password = password

    def authenticate(self):
        return True  # mock

class OAuthCredential(Credential):
    def authenticate(self):
        return True

class CertificateCredential(Credential):
    def authenticate(self):
        return True

class AuthToken(AbstractEntity):
    def __init__(self, person_id):
        super().__init__()
        self.person_id = person_id
