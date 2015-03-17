#!/bin/bash

./kill.sh jeenodes.py

python -u ./jeenodes.py >>/var/log/homeauto/jeenodes.log 2>&1 &

# FIN
