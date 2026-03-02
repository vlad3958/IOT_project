from paho.mqtt import client as mqtt_client
import json
import time
from schema.aggregated_data_schema import AggregatedDataSchema
from schema.parking_schema import ParkingSchema
from file_datasource import FileDatasource
import config
def connect_mqtt(broker, port):
    """Create MQTT client"""
    print(f"CONNECT TO {broker}:{port}")
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print(f"Connected to MQTT Broker ({broker}:{port})!")
        else:
          print(f"Failed to connect {broker}:{port}, return code {rc}\n")
          exit(rc) # Stop execution
    client = mqtt_client.Client()
    client.on_connect = on_connect
    client.connect(broker, port)
    client.loop_start()
    return client

def publish(client, datasource, delay):
    datasource.startReading()
    while True:
        time.sleep(delay)
        data = datasource.read()
        # Відправляємо aggregated у один топік, parking у інший
        agg_msg = AggregatedDataSchema().dumps(data['aggregated'])
        parking_msg = ParkingSchema().dumps(data['parking'])
        print(f"DEBUG parking_msg: {parking_msg}")
        print(f"DEBUG parking_obj: {data['parking']}")
        if not parking_msg or parking_msg == 'null':
            print("WARNING: parking_msg is empty or null! Check parking.csv and Parking object.")
        if data['parking'] is None:
            print("WARNING: parking object is None!")
        if hasattr(data['parking'], '__dict__'):
            print(f"DEBUG parking __dict__: {data['parking'].__dict__}")
        else:
            print(f"DEBUG parking type: {type(data['parking'])}")
        agg_result = client.publish(config.MQTT_TOPIC, agg_msg)
        parking_result = client.publish('parking', parking_msg)
        if agg_result[0] != 0:
            print(f"Failed to send aggregated message to topic {config.MQTT_TOPIC}")
        else:
            print(f"Sent aggregated to {config.MQTT_TOPIC}")
        if parking_result[0] != 0:
            print(f"Failed to send parking message to topic parking")
        else:
            print(f"Sent parking to parking topic")
def run():
    # Prepare mqtt client
    client = connect_mqtt(config.MQTT_BROKER_HOST, config.MQTT_BROKER_PORT)
    # Prepare datasource
    datasource = FileDatasource("accelerometer.csv", "gps.csv", "parking.csv")
    # Infinity publish data
    publish(client, datasource, config.DELAY)
if __name__ == '__main__':
    run()