import logging
from typing import Callable, List, TypeVar

import paho.mqtt.client as mqtt
from fastapi import FastAPI
from redis import Redis

from app.adapters.store_api_adapter import StoreApiAdapter
from app.entities.processed_agent_data import ProcessedAgentData
from app.entities.violation_event import ViolationEvent
from config import (
    BATCH_SIZE,
    MQTT_BROKER_HOST,
    MQTT_BROKER_PORT,
    MQTT_TOPIC,
    REDIS_HOST,
    REDIS_PORT,
    STORE_API_BASE_URL,
    VIOLATION_MQTT_TOPIC,
)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(module)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log"),
    ],
)

redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT)
store_adapter = StoreApiAdapter(api_base_url=STORE_API_BASE_URL)
app = FastAPI()
T = TypeVar("T")

PROCESSED_QUEUE_NAME = "processed_agent_data"
VIOLATION_QUEUE_NAME = "violation_events"


def enqueue_and_maybe_flush(
    queue_name: str,
    payload_json: str,
    parser: Callable[[str | bytes], T],
    saver: Callable[[List[T]], bool],
):
    redis_client.lpush(queue_name, payload_json)

    if redis_client.llen(queue_name) < BATCH_SIZE:
        return

    raw_items = redis_client.lrange(queue_name, 0, BATCH_SIZE - 1)
    batch = [parser(raw_item) for raw_item in raw_items]
    if saver(batch):
        redis_client.ltrim(queue_name, BATCH_SIZE, -1)


@app.post("/processed_agent_data/")
async def save_processed_agent_data(processed_agent_data: ProcessedAgentData):
    enqueue_and_maybe_flush(
        queue_name=PROCESSED_QUEUE_NAME,
        payload_json=processed_agent_data.model_dump_json(),
        parser=ProcessedAgentData.model_validate_json,
        saver=store_adapter.save_processed_data_batch,
    )

    return {"status": "ok"}


@app.post("/violation_events/")
async def save_violation_event(violation_event: ViolationEvent):
    enqueue_and_maybe_flush(
        queue_name=VIOLATION_QUEUE_NAME,
        payload_json=violation_event.model_dump_json(),
        parser=ViolationEvent.model_validate_json,
        saver=store_adapter.save_violation_events_batch,
    )

    return {"status": "ok"}


client = mqtt.Client()


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.info("Connected to MQTT broker")
        client.subscribe(MQTT_TOPIC)
        client.subscribe(VIOLATION_MQTT_TOPIC)
    else:
        logging.info(f"Failed to connect to MQTT broker with code: {rc}")


def on_message(client, userdata, msg):
    try:
        payload: str = msg.payload.decode("utf-8")
        if msg.topic == MQTT_TOPIC:
            processed_agent_data = ProcessedAgentData.model_validate_json(
                payload, strict=True
            )
            enqueue_and_maybe_flush(
                queue_name=PROCESSED_QUEUE_NAME,
                payload_json=processed_agent_data.model_dump_json(),
                parser=ProcessedAgentData.model_validate_json,
                saver=store_adapter.save_processed_data_batch,
            )
        elif msg.topic == VIOLATION_MQTT_TOPIC:
            violation_event = ViolationEvent.model_validate_json(payload, strict=True)
            enqueue_and_maybe_flush(
                queue_name=VIOLATION_QUEUE_NAME,
                payload_json=violation_event.model_dump_json(),
                parser=ViolationEvent.model_validate_json,
                saver=store_adapter.save_violation_events_batch,
            )
        else:
            logging.info("Ignoring message from unsupported topic: %s", msg.topic)
    except Exception as e:
        logging.info(f"Error processing MQTT message: {e}")


client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT)
client.loop_start()
