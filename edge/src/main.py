import logging
import time
from app.adapters.agent_mqtt_adapter import AgentMQTTAdapter
from app.adapters.hub_mqtt_adapter import HubMqttAdapter
from app.adapters.violation_mqtt_adapter import ViolationMqttAdapter
from app.usecases.violation_detection import ViolationDetector
from config import (
    MQTT_BROKER_HOST, MQTT_BROKER_PORT, MQTT_TOPIC,
    HUB_MQTT_BROKER_HOST, HUB_MQTT_BROKER_PORT, HUB_MQTT_TOPIC,
    VIOLATION_MQTT_TOPIC, ROADS_CONFIG_PATH, VEHICLE_ID, MIN_DIRECTION_MOVEMENT_M,
    TRAFFIC_LIGHTS_CONFIG_PATH,
    WRONG_WAY_MAX_RANDOM_INTERVAL_S,
)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] [%(module)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("app.log"),
        ],
    )

    # Hub adapter (MQTT variant - sends processed data to hub via MQTT)
    hub_adapter = HubMqttAdapter(
        broker=HUB_MQTT_BROKER_HOST,
        port=HUB_MQTT_BROKER_PORT,
        topic=HUB_MQTT_TOPIC,
    )
    violation_adapter = ViolationMqttAdapter(
        broker=HUB_MQTT_BROKER_HOST,
        port=HUB_MQTT_BROKER_PORT,
        topic=VIOLATION_MQTT_TOPIC,
    )
    violation_detector = ViolationDetector.from_json(
        roads_config_path=ROADS_CONFIG_PATH,
        traffic_lights_config_path=TRAFFIC_LIGHTS_CONFIG_PATH,
        vehicle_id=VEHICLE_ID,
        min_movement_distance_m=MIN_DIRECTION_MOVEMENT_M,
        wrong_way_max_random_interval_s=WRONG_WAY_MAX_RANDOM_INTERVAL_S,
    )

    # Agent adapter (subscribes to agent data from MQTT)
    agent_adapter = AgentMQTTAdapter(
        broker_host=MQTT_BROKER_HOST,
        broker_port=MQTT_BROKER_PORT,
        topic=MQTT_TOPIC,
        hub_gateway=hub_adapter,
        violation_gateway=violation_adapter,
        violation_detector=violation_detector,
    )

    try:
        agent_adapter.connect()
        agent_adapter.start()
        logging.info("Edge Data Logic started. Waiting for agent data...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        agent_adapter.stop()
        logging.info("System stopped.")
