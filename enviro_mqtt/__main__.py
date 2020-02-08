import sys
import argparse
from .enviro import EnviroPlus
from .mqtt import EnviroMqtt


parser = argparse.ArgumentParser(description='Send enviro+ data to MQTT')
parser.add_argument('run_mode', type=str, choices=['enviro', 'mqtt', 'all'])
parser.add_argument('--address', type=str)
parser.add_argument('--port', type=int)
parser.add_argument('--user', type=str)
parser.add_argument('--pw', type=str)
parser.add_argument('--topic', type=str)

args = parser.parse_args()

try:
    enviro = EnviroPlus()
    if args.run_mode == 'mqtt' or args.run_mode == 'all':
        mqtt = EnviroMqtt(enviro, args.address, args.port, args.topic, username=args.user, pw=args.pw)
        mqtt.start_async()

    if args.run_mode == 'enviro' or args.run_mode == 'all':
        enviro.start().join()

# Exit cleanly
except KeyboardInterrupt:
    sys.exit(0)