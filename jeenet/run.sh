#!/bin/bash

./kill.sh jeenodes.py
 
python ./jeenodes.py -d /dev/ttyUSB0 -i klatu -m mosquitto 2>/dev/null >/tmp/jeenodes.log &

# FIN
