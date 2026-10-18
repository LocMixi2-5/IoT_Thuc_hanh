import time
import sys
import paho.mqtt.client as mqtt

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def on_connect(client, userdata, flags, rc):
    print(f"Connected to broker.emqx.io with rc={rc}")
    client.subscribe("iot/B23DCCN492/#")
    client.subscribe("iot/#")
    client.subscribe("v1/#")

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode('utf-8', errors='replace')
        print(f"\n[RECEIVED] Topic={msg.topic} | Payload={payload[:120]}")
    except Exception as e:
        print("Error decoding:", e)

client = mqtt.Client(client_id="diagnose_listener_ptit_2")
client.on_connect = on_connect
client.on_message = on_message

client.connect("broker.emqx.io", 1883, 60)
client.loop_start()

for i in range(10):
    time.sleep(1)

client.loop_stop()
client.disconnect()
