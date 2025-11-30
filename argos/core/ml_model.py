from abc import ABC, abstractmethod

class MLModel(ABC):
    @abstractmethod
    def train(self, data):
        pass

    @abstractmethod
    def predict(self, x):
        pass

    @abstractmethod
    def explain(self, x):
        pass
