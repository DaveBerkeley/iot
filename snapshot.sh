#!/bin/bash

NAME="cam_0"
DEV="/dev/camera_0"

TOPIC_CAM="home/usb/0/0"
TOPIC_LAMP="home/usb/0/1"

MQTT="mosquitto"

# Turn on the camera and the lamp
echo "S" | mosquitto_pub -h $MQTT -t $TOPIC_CAM -l -r
echo "S" | mosquitto_pub -h $MQTT -t $TOPIC_LAMP -l -r

# wait for drivers to start, AGC to stabilise ..
sleep 4

P=$(date +"/usr/local/data/snap/$NAME/%Y/%m/%d/%H%M.jpg")
D=$(dirname "$P")

if [ ! -d "$D" ]; then
    echo "make $D"
    mkdir -p $D
fi

# Take the photo (camera is upside down, so flip)
fswebcam --skip 25 --flip h --flip v --device $DEV $P

# copy it somewhere we can view it on wiki
cp $P "/usr/local/data/DIGICAM/$NAME.jpg"

# turn the lamp off. Leave the camera
#echo "R" | mosquitto_pub -h $MQTT -t $TOPIC_CAM -l -r
echo "R" | mosquitto_pub -h $MQTT -t $TOPIC_LAMP -l -r

# FIN
