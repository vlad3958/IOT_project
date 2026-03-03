import logging
import requests

from app.entities.processed_agent_data import ProcessedAgentData
from app.interfaces.hub_gateway import HubGateway


class HubHttpAdapter(HubGateway):
    def __init__(self, api_base_url):
        self.api_base_url = api_base_url

    def save_data(self, processed_data: ProcessedAgentData) -> bool:
        try:
            url = f"{self.api_base_url}/processed_agent_data/"
            response = requests.post(url, json=processed_data.model_dump(mode="json"))
            if response.status_code in (200, 201):
                logging.info("Successfully sent processed data to hub via HTTP")
                return True
            else:
                logging.error(f"Hub HTTP returned status: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            logging.error(f"Connection error to hub: {e}")
            return False
