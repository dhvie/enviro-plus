from bme280 import BME280
from pms5003 import PMS5003, ReadTimeoutError as pmsReadTimeoutError
from enviroplus import gas
from subprocess import PIPE, Popen
import ST7735
import os
import logging
import colorsys
from collections import deque, defaultdict
import pandas as pd
import math
from multiprocessing import Process

try:
    # Transitional fix for breaking change in LTR559
    from ltr559 import LTR559

    ltr559 = LTR559()
except ImportError:
    import ltr559

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

sensor_list = ["temperature",
               "pressure",
               "humidity",
               "light",
               "oxidised",
               "reduced",
               "nh3",
               "pm1",
               "pm25",
               "pm10"]

unit_list = ["C",
             "hPa",
             "%",
             "Lux",
             "kO",
             "kO",
             "kO",
             "ug/m3",
             "ug/m3",
             "ug/m3"]


class EnviroLCD:

    def __init__(self):
        # Create ST7735 LCD display class
        self.__lcd = ST7735.ST7735(
            port=0,
            cs=1,
            dc=9,
            backlight=12,
            rotation=270,
            spi_speed_hz=10000000
        )

        self.__lcd.begin()

        self.__image = Image.new('RGB', (self.__lcd.width, self.__lcd.height), color=(0, 0, 0))
        self.__draw = ImageDraw.Draw(self.__image)

        path = os.path.dirname(os.path.realpath(__file__))
        self.__font = ImageFont.truetype(path + "/fonts/Asap/Asap-Bold.ttf", 20)
        self.__smallfont = ImageFont.truetype(path + "/fonts/Asap/Asap-Bold.ttf", 10)

        self.__message = ""

        # The position of the top bar
        self.__top_pos = 25

    @property
    def width(self):
        return self.__lcd.width

    @property
    def height(self):
        return self.__lcd.height

    # Displays data and text on the 0.96" LCD
    def display_series(self, title, data, unit):
        # Maintain length of list
        plot_values = data
        if len(data) > self.__lcd.width:
            plot_values = data[-self.width]

        # Scale the values for the variable between 0 and 1
        colours = (plot_values - plot_values.min() + 1) / (plot_values.max() - plot_values.min() + 1)
        # Format the variable name and value
        message = "{}: {:.1f} {}".format(title[:4], data, unit)
        logging.info(message)
        self.__draw.rectangle((0, 0, self.width, self.height), (255, 255, 255))
        for i, value in enumerate(colours):
            # Convert the values to colours from red to blue
            colour = (1.0 - value) * 0.6
            r, g, b = [int(x * 255.0) for x in colorsys.hsv_to_rgb(colour,
                                                                   1.0, 1.0)]
            # Draw a 1-pixel wide rectangle of colour
            self.__draw.rectangle((i, self.__top_pos, i + 1, self.height), (r, g, b))
            # Draw a line graph in black
            line_y = self.height - (self.__top_pos + (colours[i] * (self.height - self.__top_pos))) \
                     + self.__top_pos
            self.__draw.rectangle((i, line_y, i + 1, line_y + 1), (0, 0, 0))
        # Write the text at the top in black
        self.__draw.text((0, 0), message, font=self.__font, fill=(0, 0, 0))
        self.display(self.__image)

    # Displays all the text on the 0.96" LCD
    def display_dict(self, d, units=None, conditional_formatting=None, color_pallet=None):
        if units is None:
            units = pd.DataFrame(
                data=unit_list,
                columns=['value'],
                index=sensor_list
            )

        if conditional_formatting is None:
            conditional_formatting = pd.DataFrame(
                data=[
                    [4, 18, 28, 35],
                    [250, 650, 1013.25, 1015],
                    [20, 30, 60, 70],
                    [-1, -1, 30000, 100000],
                    [-1, -1, 40, 50],
                    [-1, -1, 450, 550],
                    [-1, -1, 200, 300],
                    [-1, -1, 50, 100],
                    [-1, -1, 50, 100],
                    [-1, -1, 50, 100]
                ],
                index=sensor_list,
                columns=['limit_low', 'limit_normal', 'limit_high', 'limit_highest'],
                dtype=float
            )

        if color_pallet is None:
            color_pallet = {
                'danger_low': (0, 0, 255),
                'low': (0, 0, 255),
                'normal': (0, 255, 0),
                'high': (255, 255, 0),
                'danger_high': (255, 0, 0)
            }

        self.__draw.rectangle((0, 0, self.width, self.height), (0, 0, 0))
        column_count = 2
        x_offset = 2
        y_offset = 2
        row_count = math.ceil(len(d) / column_count)
        i = 0
        for name, value in d.items():
            unit = units.get(name)
            x = x_offset + ((self.width / column_count) * (i / row_count))
            y = y_offset + ((self.height / row_count) * (i % row_count))
            message = "{}: {:.1f} {}".format(name[:4], value, unit)
            limits = conditional_formatting.loc[name]
            print(limits)
            max_level = ""
            for limit in limits.columns:
                if value > limits[limit]:
                    max_level = limit

            if max_level == "":
                rgb = color_pallet['danger_low']
            elif max_level == "limit_low":
                rgb = color_pallet['low']
            elif max_level == "limit_normal":
                rgb = color_pallet['normal']
            elif max_level == "limit_high":
                rgb = color_pallet['high']
            else:
                rgb = color_pallet['danger_high']

            self.__draw.text((x, y), message, font=self.__smallfont, fill=rgb)
            i += 1

        self.display(self.__image)

    def display(self, img):
        self.__lcd.display(img)


class EnviroPlus:

    def __init__(self):
        # BME280 temperature/pressure/humidity sensor
        self.__bme280 = BME280()

        # PMS5003 particulate sensor
        self.__pms5003 = PMS5003()

        self.__ltr559 = ltr559

        self.__lcd = EnviroLCD()
        self.__cpu_temp_history = deque([self.__get_cpu_temperature()] * 15)

        self.__update_proc = None

    # Get the temperature of the CPU for compensation
    def __get_cpu_temperature(self):
        process = Popen(['vcgencmd', 'measure_temp'], stdout=PIPE, universal_newlines=True)
        output, _error = process.communicate()
        return float(output[output.index('=') + 1:output.rindex("'")])

    @property
    def temperature(self):
        self.__cpu_temp_history.append(self.__get_cpu_temperature())
        avg_cpu_temp = sum(self.__cpu_temp_history) / float(len(self.__cpu_temp_history))
        self.__cpu_temp_history.popleft()
        temp_reading = self.__bme280.get_temperature()
        return temp_reading - (avg_cpu_temp - temp_reading) / 1.95

    @property
    def pressure(self):
        return self.__bme280.get_pressure()

    @property
    def humidity(self):
        return self.__bme280.get_humidity()

    @property
    def gas(self):
        gas_data = gas.read_all()
        return {
            'oxidising': gas_data.oxidising / 1000,
            'reducing': gas_data.reducing / 1000,
            'nh3': gas_data.nh3 / 1000
        }

    @property
    def particulates(self):
        try:
            pms_data = self.__pms5003.read()
        except pmsReadTimeoutError:
            logging.warning('Failed to read PMS5003')
            return defaultdict(int)
        return {
            'pm1': float(pms_data.pm_ug_per_m3(1.0)),
            'pm25': float(pms_data.pm_ug_per_m3(2.5)),
            'pm10': float(pms_data.pm_ug_per_m3(10))
        }

    @property
    def lux(self):
        return self.__ltr559.get_lux()

    def display_img(self, img):
        self.__lcd.display(img)

    def display_all(self):
        gas = self.gas
        pms = self.particulates
        self.__lcd.display_dict({
            "temperature": self.temperature,
            "pressure": self.pressure,
            "humidity": self.humidity,
            "oxidised": gas['oxidising'],
            "reducing": gas['reducing'],
            "nh3": gas['nh3'],
            "pm1": pms['pm1'],
            "pm25": pms['pm25'],
            "pm10": pms['pm10'],
            "light": self.lux
        })

    def start(self):
        if self.__update_proc is not None:
            self.__update_proc = Process(target=self.display_all)

    def stop(self):
        if self.__update_proc is not None:
            self.__update_proc.terminate()
        self.__update_proc = None
