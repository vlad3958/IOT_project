import json
import logging

import paho.mqtt.client as mqtt

from app.entities.processed_agent_data import ProcessedAgentData
from app.interfaces.hub_gateway import HubGateway


class HubMqttAdapter(HubGateway):
    def __init__(self, broker, port, topic):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.client = mqtt.Client()
        self.client.connect(broker, port)
        self.client.loop_start()
        logging.info(f"HubMqttAdapter connected to {broker}:{port}, topic={topic}")

    def save_data(self, processed_data: ProcessedAgentData) -> bool:
        try:
            msg = processed_data.model_dump_json()
            result = self.client.publish(self.topic, msg)
            if result[0] == 0:
                logging.info(f"Sent processed data to hub topic '{self.topic}'")
                return True
            else:
                logging.error(f"Failed to send data to hub topic '{self.topic}'")
                return False
        except Exception as e:
            logging.error(f"Error sending data to hub: {e}")
            return False
