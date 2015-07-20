#!/bin/bash

./kill.sh jeenodes.py
 
cp /tmp/jeenodes.log /tmp/jeenodes.log.old

python -u ./jeenodes.py 2>/tmp/jeenodes.log >/dev/null &

# FIN
