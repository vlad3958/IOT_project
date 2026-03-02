import logging
from typing import List
import requests

from app.entities.processed_agent_data import ProcessedAgentData
from app.interfaces.store_gateway import StoreGateway


class StoreApiAdapter(StoreGateway):
    def __init__(self, api_base_url):
        self.api_base_url = api_base_url

    def save_data(self, processed_agent_data_batch: List[ProcessedAgentData]) -> bool:
        """
        Make a POST request to the Store API endpoint with the processed data
        """
        # 1. Формуємо URL до ендпоінту Store API (з Лаби №2)
        # Зверніть увагу: на кінці має бути слеш, якщо так налаштовано у FastAPI
        url = f"{self.api_base_url}/processed_agent_data/"

        # 2. Перетворюємо список об'єктів Pydantic у список словників для відправки
        # Використовуємо .model_dump() для Pydantic v2 (який використовується у вас)
        data_to_send = [item.model_dump(mode='json')
                        for item in processed_agent_data_batch]

        try:
            # 3. Відправляємо POST-запит з даними у форматі JSON
            response = requests.post(url, json=data_to_send)

            # 4. Перевіряємо успішність запиту (код 200 OK або 201 Created)
            if response.status_code in (200, 201, 202):
                logging.info(
                    f"Successfully saved batch of {len(processed_agent_data_batch)} records to Store API.")
                return True
            else:
                logging.error(
                    f"Failed to save data. Store API returned status: {response.status_code}. Details: {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            # Обробка помилок (наприклад, якщо Store API впав або недоступний по мережі)
            logging.error(
                f"Connection error while sending data to Store API: {e}")
            return False
