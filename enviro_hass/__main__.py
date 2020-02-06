import time
import colorsys
import os
import sys
import ST7735
import json
try:
    # Transitional fix for breaking change in LTR559
    from ltr559 import LTR559
    ltr559 = LTR559()
except ImportError:
    import ltr559

from bme280 import BME280
from pms5003 import PMS5003, ReadTimeoutError as pmsReadTimeoutError
from enviroplus import gas
from subprocess import PIPE, Popen
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
import logging
import paho.mqtt.client as mqtt
import argparse

# BME280 temperature/pressure/humidity sensor
bme280 = BME280()

# PMS5003 particulate sensor
pms5003 = PMS5003()

# Create ST7735 LCD display class
st7735 = ST7735.ST7735(
    port=0,
    cs=1,
    dc=9,
    backlight=12,
    rotation=270,
    spi_speed_hz=10000000
)

# Initialize display
st7735.begin()

WIDTH = st7735.width
HEIGHT = st7735.height

# Set up canvas and font
img = Image.new('RGB', (WIDTH, HEIGHT), color=(0, 0, 0))
draw = ImageDraw.Draw(img)
path = os.path.dirname(os.path.realpath(__file__))
font = ImageFont.truetype(path + "/fonts/Asap/Asap-Bold.ttf", 20)
smallfont = ImageFont.truetype(path + "/fonts/Asap/Asap-Bold.ttf", 10)
x_offset = 2
y_offset = 2

message = ""

# The position of the top bar
top_pos = 25

# Create a values dict to store the data
variables = ["temperature",
             "pressure",
             "humidity",
             "light",
             "oxidised",
             "reduced",
             "nh3",
             "pm1",
             "pm25",
             "pm10"]

units = ["C",
         "hPa",
         "%",
         "Lux",
         "kO",
         "kO",
         "kO",
         "ug/m3",
         "ug/m3",
         "ug/m3"]

# Define your own warning limits
# The limits definition follows the order of the variables array
# Example limits explanation for temperature:
# [4,18,28,35] means
# [-273.15 .. 4] -> Dangerously Low
# (4 .. 18]      -> Low
# (18 .. 28]     -> Normal
# (28 .. 35]     -> High
# (35 .. MAX]    -> Dangerously High
# DISCLAIMER: The limits provided here are just examples and come
# with NO WARRANTY. The authors of this example code claim
# NO RESPONSIBILITY if reliance on the following values or this
# code in general leads to ANY DAMAGES or DEATH.
limits = [[4,18,28,35],
          [250,650,1013.25,1015],
          [20,30,60,70],
          [-1,-1,30000,100000],
          [-1,-1,40,50],
          [-1,-1,450,550],
          [-1,-1,200,300],
          [-1,-1,50,100],
          [-1,-1,50,100],
          [-1,-1,50,100]]

# RGB palette for values on the combined screen
palette = [(0,0,255),           # Dangerously Low
           (0,255,255),         # Low
           (0,255,0),           # Normal
           (255,255,0),         # High
           (255,0,0)]           # Dangerously High

values = {}


# Displays data and text on the 0.96" LCD
def display_text(variable, data, unit):
    # Maintain length of list
    values[variable] = values[variable][1:] + [data]
    # Scale the values for the variable between 0 and 1
    colours = [(v - min(values[variable]) + 1) / (max(values[variable])
                                                  - min(values[variable]) + 1) for v in values[variable]]
    # Format the variable name and value
    message = "{}: {:.1f} {}".format(variable[:4], data, unit)
    logging.info(message)
    draw.rectangle((0, 0, WIDTH, HEIGHT), (255, 255, 255))
    for i in range(len(colours)):
        # Convert the values to colours from red to blue
        colour = (1.0 - colours[i]) * 0.6
        r, g, b = [int(x * 255.0) for x in colorsys.hsv_to_rgb(colour,
                                                               1.0, 1.0)]
        # Draw a 1-pixel wide rectangle of colour
        draw.rectangle((i, top_pos, i+1, HEIGHT), (r, g, b))
        # Draw a line graph in black
        line_y = HEIGHT - (top_pos + (colours[i] * (HEIGHT - top_pos))) \
                 + top_pos
        draw.rectangle((i, line_y, i+1, line_y+1), (0, 0, 0))
    # Write the text at the top in black
    draw.text((0, 0), message, font=font, fill=(0, 0, 0))
    st7735.display(img)

# Saves the data to be used in the graphs later and prints to the log
def save_data(idx, data):
    variable = variables[idx]
    # Maintain length of list
    values[variable] = values[variable][1:] + [data]
    unit = units[idx]
    message = "{}: {:.1f} {}".format(variable[:4], data, unit)
    logging.info(message)


# Displays all the text on the 0.96" LCD
def display_everything():
    draw.rectangle((0, 0, WIDTH, HEIGHT), (0, 0, 0))
    column_count = 2
    row_count = (len(variables)/column_count)
    for i in range(len(variables)):
        variable = variables[i]
        data_value = values[variable][-1]
        unit = units[i]
        x = x_offset + ((WIDTH/column_count) * (i / row_count))
        y = y_offset + ((HEIGHT/row_count) * (i % row_count))
        message = "{}: {:.1f} {}".format(variable[:4], data_value, unit)
        lim = limits[i]
        rgb = palette[0]
        for j in range(len(lim)):
            if data_value > lim[j]:
                rgb = palette[j+1]
        draw.text((x, y), message, font=smallfont, fill=rgb)
    st7735.display(img)



# Get the temperature of the CPU for compensation
def get_cpu_temperature():
    process = Popen(['vcgencmd', 'measure_temp'], stdout=PIPE, universal_newlines=True)
    output, _error = process.communicate()
    return float(output[output.index('=') + 1:output.rindex("'")])


def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))


# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    print(msg.topic+" "+str(msg.payload))

parser = argparse.ArgumentParser(description='Send enviro+ data to MQTT')
parser.add_argument('--address', type=str)
parser.add_argument('--port', type=int)
parser.add_argument('--user', type=str)
parser.add_argument('--pw', type=str)
parser.add_argument('--topic', type=str)

args = parser.parse_args()


client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.username_pw_set(args.user, password=args.pw)
client.connect(args.address, args.port, 60)
client.loop_start()


# Tuning factor for compensation. Decrease this number to adjust the
# temperature down, and increase to adjust up
factor = 1.95

cpu_temps = [get_cpu_temperature()] * 5

delay = 0.5  # Debounce the proximity tap
mode = 10    # The starting mode
last_page = 0
light = 1

for v in variables:
    values[v] = [1] * WIDTH

# The main loop
try:
    while True:
        mqtt_res = dict()

        # Everything on one screen
        cpu_temp = get_cpu_temperature()
        # Smooth out with some averaging to decrease jitter
        cpu_temps = cpu_temps[1:] + [cpu_temp]
        avg_cpu_temp = sum(cpu_temps) / float(len(cpu_temps))
        raw_temp = bme280.get_temperature()
        raw_data = raw_temp - ((avg_cpu_temp - raw_temp) / factor)
        mqtt_res['temp'] = raw_data
        save_data(0, raw_data)
        display_everything()

        raw_data = bme280.get_pressure()
        mqtt_res['pressure'] = raw_data
        save_data(1, raw_data)
        display_everything()

        raw_data = bme280.get_humidity()
        mqtt_res['humidity'] = raw_data
        save_data(2, raw_data)

        gas_data = gas.read_all()
        gas_ox = gas_data.oxidising / 1000
        gas_red = gas_data.reducing / 1000
        gas_nh3 = gas_data.nh3 / 1000
        save_data(4, gas_ox)
        save_data(5, gas_red)
        save_data(6, gas_nh3)
        mqtt_res['gas_ox'] = gas_ox
        mqtt_res['gas_reg'] = gas_red
        mqtt_res['gas_nh3'] = gas_nh3
        display_everything()
        pms_data = None
        try:
            pms_data = pms5003.read()
        except pmsReadTimeoutError:
            logging.warning("Failed to read PMS5003")
        else:
            pms1 = float(pms_data.pm_ug_per_m3(1.0))
            pms25 = float(pms_data.pm_ug_per_m3(2.5))
            pms10 = float(pms_data.pm_ug_per_m3(10))
            save_data(7, pms1)
            save_data(8, pms25)
            save_data(9, pms10)
            mqtt_res['pms1'] = pms1
            mqtt_res['pms25'] = pms25
            mqtt_res['pms10'] = pms10
            display_everything()
        client.publish(args.topic, payload=json.dumps(mqtt_res))

# Exit cleanly
except KeyboardInterrupt:
    sys.exit(0)