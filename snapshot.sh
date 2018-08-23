#!/bin/bash

NAME="cam_0"
DEV="/dev/camera_0"

TOPIC_CAM="home/usb/0/0"
TOPIC_LAMP="home/usb/0/1"

MQTT="mosquitto"

# Turn on the camera and the lamp
echo "S" | mosquitto_pub -h $MQTT -t $TOPIC_CAM -l
echo "S" | mosquitto_pub -h $MQTT -t $TOPIC_LAMP -l

# wait for drivers to start, AGC to stabilise ..
sleep 4

P=$(date +"/usr/local/data/snap/$NAME/%Y/%m/%d/%H%M.jpg")
D=$(dirname "$P")

if [ ! -d "$D" ]; then
    echo "make $D"
    mkdir -p $D
fi

# Take the photo
fswebcam --device $DEV $P

# turn the lamp off. Leave the camera
#echo "R" | mosquitto_pub -h $MQTT -t $TOPIC_CAM -l
echo "R" | mosquitto_pub -h $MQTT -t $TOPIC_LAMP -l

# FIN
