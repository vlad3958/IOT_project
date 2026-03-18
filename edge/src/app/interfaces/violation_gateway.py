from abc import ABC, abstractmethod

from app.entities.violation_event import ViolationEvent


class ViolationGateway(ABC):
    @abstractmethod
    def save_violation(self, violation_event: ViolationEvent) -> bool:
        """
        Publish or persist a violation event.
        """
        pass
