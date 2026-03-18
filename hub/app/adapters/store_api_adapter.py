import logging
from typing import List

import requests

from app.entities.processed_agent_data import ProcessedAgentData
from app.entities.violation_event import ViolationEvent
from app.interfaces.store_gateway import StoreGateway


class StoreApiAdapter(StoreGateway):
    def __init__(self, api_base_url):
        self.api_base_url = api_base_url

    def save_processed_data_batch(
        self,
        processed_agent_data_batch: List[ProcessedAgentData],
    ) -> bool:
        url = f"{self.api_base_url}/processed_agent_data/"
        data_to_send = [
            item.model_dump(mode="json") for item in processed_agent_data_batch
        ]

        try:
            response = requests.post(url, json=data_to_send)
            if response.status_code in (200, 201, 202):
                logging.info(
                    "Successfully saved batch of %s records to Store API.",
                    len(processed_agent_data_batch),
                )
                return True
            logging.error(
                "Failed to save data. Store API returned status: %s. Details: %s",
                response.status_code,
                response.text,
            )
            return False

        except requests.exceptions.RequestException as exc:
            logging.error(
                "Connection error while sending data to Store API: %s",
                exc,
            )
            return False

    def save_violation_events_batch(
        self,
        violation_events_batch: List[ViolationEvent],
    ) -> bool:
        url = f"{self.api_base_url}/violation_events/"
        data_to_send = [
            item.model_dump(mode="json") for item in violation_events_batch
        ]

        try:
            response = requests.post(url, json=data_to_send)
            if response.status_code in (200, 201, 202):
                logging.info(
                    "Successfully saved batch of %s violation event(s) to Store API.",
                    len(violation_events_batch),
                )
                return True
            logging.error(
                "Failed to save violation events. Store API returned status: %s. Details: %s",
                response.status_code,
                response.text,
            )
            return False
        except requests.exceptions.RequestException as exc:
            logging.error(
                "Connection error while sending violation events to Store API: %s",
                exc,
            )
            return False
