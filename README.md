# Pimoroni Enviro+ MQTT

##Installation
1. Follow the installation instructions on https://github.com/pimoroni/enviroplus-python as this will install packages we depend on
2. Install numpy and pandas - depending on your platform you can do this with either with pip or otherwise use:
    ```shell script
    sudo apt-get install python3-numpy python3-pandas
    ```
3. Clone this repo and cd into it.
4. Install the package into your environment
    ```shell script
    pip3 install .
    ```
    All dependencies should be found, if not they should be simple to install via `pip3 install`
    
##Usage
You can simply run the package using `python3 -m enviro_mqtt <enviro|mqtt|all>`
The argument tells enviro if you want to just display the sensor measurments on screen (`enviro`) or just send via
mqtt and keep the screen blank (`mqtt`) or you want to do both (`all`)

If you want to send data via mqtt you need to specify your MQTT broker details using the following parameters:
```shell script
--address <your_broker_ip>
--port <your_broker_port>
--user <your_client_user_name>
--pw <your_client_password>
--topic <the_topic_to_publish_on>
```
After you hit enter the screen should come alive and soon after you will start seeing data coming in on your MQTT broker
if all the details are correct and your user has write access to the topic you specified.

The data has the form:
```json
{
  'temp': <float>,
  'pressure': <float>,
  'humidity': <float>,
  'gas_oxidising': <float>,
  'gas_reducing': <float>,
  'gas_nh3':<float>,
  'pm1': <int>,
  'pm25': <int>,
  'pm10': <int>
}
```

If you find any issues feel free to post in issues or submit a PR

Enjoy!