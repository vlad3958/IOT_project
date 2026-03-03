import logging
from app.adapters.agent_mqtt_adapter import AgentMQTTAdapter
from app.adapters.hub_http_adapter import HubHttpAdapter
from app.adapters.hub_mqtt_adapter import HubMqttAdapter
from config import (
    MQTT_BROKER_HOST, MQTT_BROKER_PORT, MQTT_TOPIC,
    HUB_URL, HUB_MQTT_BROKER_HOST, HUB_MQTT_BROKER_PORT, HUB_MQTT_TOPIC,
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

    # Agent adapter (subscribes to agent data from MQTT)
    agent_adapter = AgentMQTTAdapter(
        broker_host=MQTT_BROKER_HOST,
        broker_port=MQTT_BROKER_PORT,
        topic=MQTT_TOPIC,
        hub_gateway=hub_adapter,
    )

    try:
        agent_adapter.connect()
        agent_adapter.start()
        logging.info("Edge Data Logic started. Waiting for agent data...")
        while True:
            pass
    except KeyboardInterrupt:
        agent_adapter.stop()
        logging.info("System stopped.")
