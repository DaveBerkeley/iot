#!/bin/bash

./kill.sh jeenodes.py
 
# cp /tmp/jeenodes.log /tmp/jeenodes.log.old

python ./jeenodes.py -im 2>/dev/null >/dev/null &

# FIN
