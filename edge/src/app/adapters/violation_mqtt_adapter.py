import logging

import paho.mqtt.client as mqtt

from app.entities.violation_event import ViolationEvent
from app.interfaces.violation_gateway import ViolationGateway


class ViolationMqttAdapter(ViolationGateway):
    def __init__(self, broker, port, topic):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.client = mqtt.Client()
        self.client.connect(broker, port)
        self.client.loop_start()
        logging.info(
            "ViolationMqttAdapter connected to %s:%s, topic=%s",
            broker,
            port,
            topic,
        )

    def save_violation(self, violation_event: ViolationEvent) -> bool:
        try:
            msg = violation_event.model_dump_json()
            result = self.client.publish(self.topic, msg)
            if result[0] == 0:
                logging.info("Sent violation event to topic '%s'", self.topic)
                return True
            logging.error("Failed to send violation event to topic '%s'", self.topic)
            return False
        except Exception as exc:
            logging.error("Error sending violation event: %s", exc)
            return False
