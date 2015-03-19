#!/bin/bash

./kill.sh jeenodes.py

python -u ./jeenodes.py >/tmp/jeenodes.log 2>&1 &

# FIN
