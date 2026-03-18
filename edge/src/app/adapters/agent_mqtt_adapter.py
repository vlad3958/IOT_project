import json
import logging
from datetime import datetime

import paho.mqtt.client as mqtt

from app.entities.agent_data import AgentData, AccelerometerData, GpsData
from app.interfaces.agent_gateway import AgentGateway
from app.interfaces.hub_gateway import HubGateway
from app.interfaces.violation_gateway import ViolationGateway
from app.usecases.data_processing import process_agent_data
from app.usecases.violation_detection import ViolationDetector


class AgentMQTTAdapter(AgentGateway):
    def __init__(
        self,
        broker_host,
        broker_port,
        topic,
        hub_gateway: HubGateway,
        violation_gateway: ViolationGateway | None = None,
        violation_detector: ViolationDetector | None = None,
    ):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topic = topic
        self.hub_gateway = hub_gateway
        self.violation_gateway = violation_gateway
        self.violation_detector = violation_detector
        self.client = mqtt.Client()
        self.previous_agent_data: AgentData | None = None

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            logging.info(f"Received message from agent: {payload}")

            # Parse agent data from the MQTT message (marshmallow format from agent)
            accelerometer = AccelerometerData(
                x=float(payload.get("accelerometer", {}).get("x", 0)),
                y=float(payload.get("accelerometer", {}).get("y", 0)),
                z=float(payload.get("accelerometer", {}).get("z", 0)),
            )
            gps = GpsData(
                latitude=float(payload.get("gps", {}).get("latitude", 0)),
                longitude=float(payload.get("gps", {}).get("longitude", 0)),
            )
            timestamp = payload.get("time") or payload.get("timestamp") or datetime.now().isoformat()

            agent_data = AgentData(
                accelerometer=accelerometer,
                gps=gps,
                timestamp=timestamp,
            )

            # Process the data (classify road state)
            processed_data = process_agent_data(agent_data)
            logging.info(f"Processed data: road_state={processed_data.road_state}")

            # Send processed data to hub
            self.hub_gateway.save_data(processed_data)

            if self.violation_detector and self.violation_gateway:
                violations = self.violation_detector.detect(
                    current_agent_data=agent_data,
                    previous_agent_data=self.previous_agent_data,
                )
                for violation in violations:
                    self.violation_gateway.save_violation(violation)

            self.previous_agent_data = agent_data

        except Exception as e:
            logging.error(f"Error processing agent message: {e}")

    def connect(self):
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                logging.info(f"Connected to MQTT broker ({self.broker_host}:{self.broker_port})")
                client.subscribe(self.topic)
                logging.info(f"Subscribed to topic: {self.topic}")
            else:
                logging.error(f"Failed to connect to MQTT broker, return code: {rc}")

        self.client.on_connect = on_connect
        self.client.on_message = self.on_message
        self.client.connect(self.broker_host, self.broker_port)

    def start(self):
        self.client.loop_start()

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()
