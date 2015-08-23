#!/bin/bash

./kill.sh jeenodes.py
 
# cp /tmp/jeenodes.log /tmp/jeenodes.log.old

python -u ./jeenodes.py 2>&1 >/dev/null &

# FIN
