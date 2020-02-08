import json
import paho.mqtt.client as mqtt
from multiprocessing import Process
from .enviro import EnviroPlus

def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))


# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    print(msg.topic+" "+str(msg.payload))


class EnviroMqtt:

    def __init__(self, enviro: EnviroPlus, broker_address, broker_port, topic, username=None, pw=None):
        self.__enviro = enviro
        self.__client = mqtt.Client()
        self.__client.on_connect = on_connect
        self.__client.on_message = on_message
        self.__client.connect(broker_address, broker_port, 60)
        self.__started = False
        self.__topic = topic

        if username is not None:
            self.__client.username_pw_set(username, password=pw)

    @property
    def enviro(self):
        return self.__enviro

    def start_async(self):
        if not self.__started:
            self.__client.loop_start()

        p = Process(target=self.__loop)
        p.start()

    def __loop(self):
        while True:
            mqtt_res = dict()
            mqtt_res['temp'] = self.__enviro.temperature
            mqtt_res['pressure'] = self.__enviro.pressure
            mqtt_res['humidity'] = self.__enviro.humidity
            gas = self.__enviro.gas
            mqtt_res['gas_ox'] = gas['oxidising']
            mqtt_res['gas_reg'] = gas['reducing']
            mqtt_res['gas_nh3'] = gas['nh3']

            particulates = self.__enviro.particulates
            mqtt_res['pm1'] = particulates['pm1']
            mqtt_res['pm25'] = particulates['pm25']
            mqtt_res['pm10'] = particulates['pm10']
            self.__client.publish(self.__topic, payload=json.dumps(mqtt_res))
