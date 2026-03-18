import os


def try_parse_int(value: str):
    try:
        return int(value)
    except Exception:
        return None


def try_parse_float(value: str):
    try:
        return float(value)
    except Exception:
        return None


# Configuration for agent MQTT
MQTT_BROKER_HOST = os.environ.get("MQTT_BROKER_HOST") or "localhost"
MQTT_BROKER_PORT = try_parse_int(os.environ.get("MQTT_BROKER_PORT")) or 1883
MQTT_TOPIC = os.environ.get("MQTT_TOPIC") or "agent_data_topic"

# Configuration for hub MQTT
HUB_MQTT_BROKER_HOST = os.environ.get("HUB_MQTT_BROKER_HOST") or "localhost"
HUB_MQTT_BROKER_PORT = try_parse_int(
    os.environ.get("HUB_MQTT_BROKER_PORT")) or 1883
HUB_MQTT_TOPIC = os.environ.get("HUB_MQTT_TOPIC") or "processed_data_topic"
VIOLATION_MQTT_TOPIC = os.environ.get(
    "VIOLATION_MQTT_TOPIC") or "violation_events"

# Configuration for hub HTTP
HUB_HOST = os.environ.get("HUB_HOST") or "localhost"
HUB_PORT = try_parse_int(os.environ.get("HUB_PORT")) or 8000
HUB_URL = f"http://{HUB_HOST}:{HUB_PORT}"

# Vehicle and road rule simulation
VEHICLE_ID = os.environ.get("VEHICLE_ID") or "demo-car-1"
ROADS_CONFIG_PATH = os.environ.get("ROADS_CONFIG_PATH") or os.path.join(
    os.path.dirname(__file__),
    "roads.json",
)
TRAFFIC_LIGHTS_CONFIG_PATH = os.environ.get("TRAFFIC_LIGHTS_CONFIG_PATH") or os.path.join(
    os.path.dirname(__file__),
    "traffic_lights.json",
)
MIN_DIRECTION_MOVEMENT_M = (
    try_parse_float(os.environ.get("MIN_DIRECTION_MOVEMENT_M")) or 5.0
)
WRONG_WAY_MAX_RANDOM_INTERVAL_S = (
    try_parse_float(os.environ.get("WRONG_WAY_MAX_RANDOM_INTERVAL_S")) or 30.0
)
