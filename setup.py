from setuptools import setup

setup(
    name='environ_hass',
    version='0.1',
    packages=['enviro_hass'],
    url='',
    license='MIT',
    author='dh_vie',
    author_email='',
    description='',
    install_requires=[
        "ST7735",
        "ltr559",
        "pimoroni-bme280",
        "pms5003",
        "PIL",
        "paho-mqtt",
        "sounddevice"
    ]
)
