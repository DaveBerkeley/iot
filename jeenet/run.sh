#!/bin/bash

./kill.sh jeenodes.py
 
# cp /tmp/jeenodes.log /tmp/jeenodes.log.old

python -u ./jeenodes.py -d /dev/ttyUSB0 -i klatu -m mosquitto 2>/dev/null >/tmp/jeenodes.log &

# FIN
