import json
import paho.mqtt.client as mqtt
import time
from functools import partial
from multiprocessing import Process
from .enviro import EnviroPlus


# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    print(msg.topic+" "+str(msg.payload))


def on_connect(client, userdata, rc):
    print("Connected with result code "+str(rc))


class EnviroMqtt:

    def __init__(self, enviro: EnviroPlus, broker_address, broker_port, topic, username=None, pw=None):
        self.__enviro = enviro
        self.__client = mqtt.Client()
        self.__client.on_connect = on_connect
        self.__client.on_message = on_message
        self.__started = False
        self.__topic = topic
        self.__broker = broker_address
        self.__port = broker_port
        self.__run_loop = None
        self.__client.reconnect_delay_set(min_delay=1, max_delay=300)

        if username is not None:
            self.__client.username_pw_set(username, password=pw)

    @property
    def enviro(self):
        return self.__enviro

    def start_blocking(self):
        if not self.__started:
            self.__started = True
            self.__client.connect(self.__broker, self.__port, 60)
            self.__client.loop_start()
            self.__loop()

    def stop(self):
        if self.__started:
            try:
                self.__client.disconnect()
            except Exception as e:
                print(e)
            finally:
                self.__started = False

    def __loop(self):
        while True:
            mqtt_res = dict()
            mqtt_res['temp'] = "{:.2f}".format(self.__enviro.temperature)
            mqtt_res['pressure'] = "{:.2f}".format(self.__enviro.pressure)
            mqtt_res['humidity'] = "{:.2f}".format(self.__enviro.humidity)
            gas = self.__enviro.gas
            mqtt_res['gas_ox'] = "{:.2f}".format(gas['oxidising'])
            mqtt_res['gas_reg'] = "{:.2f}".format(gas['reducing'])
            mqtt_res['gas_nh3'] = "{:.2f}".format(gas['nh3'])

            particulates = self.__enviro.particulates
            mqtt_res['pm1'] = particulates['pm1']
            mqtt_res['pm25'] = particulates['pm25']
            mqtt_res['pm10'] = particulates['pm10']
            self.__client.publish(self.__topic, payload=json.dumps(mqtt_res))
