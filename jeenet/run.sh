#!/bin/bash

./kill.sh jeenodes.py
 
cp /tmp/jeenodes.log /tmp/jeenodes.log.old
python -u ./jeenodes.py >/tmp/jeenodes.log 2>&1 &

# FIN
