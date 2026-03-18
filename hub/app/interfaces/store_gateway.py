from abc import ABC, abstractmethod
from typing import List

from app.entities.processed_agent_data import ProcessedAgentData
from app.entities.violation_event import ViolationEvent


class StoreGateway(ABC):
    """
    Abstract class representing the Store Gateway interface.
    All store gateway adapters must implement these methods.
    """

    @abstractmethod
    def save_processed_data_batch(
        self,
        processed_data_batch: List[ProcessedAgentData],
    ) -> bool:
        """
        Save a batch of processed agent data in the database.
        """
        pass

    @abstractmethod
    def save_violation_events_batch(
        self,
        violation_events_batch: List[ViolationEvent],
    ) -> bool:
        """
        Save a batch of violation events in the database.
        """
        pass
