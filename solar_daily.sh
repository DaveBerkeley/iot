#!/bin/bash

# Calculate the solar energy produced yesterday.
# Email the info.

FILENAME=$(date --date="yesterday" +"/usr/local/data/solar/%Y/%m/%d.log")

#echo $FILENAME

HEAD=$(head -n 1 $FILENAME | awk '//{print $2}')
TAIL=$(tail -n 1 $FILENAME | awk '//{print $2}')

#echo $HEAD
#echo $TAIL

DIFF=$(($TAIL - $HEAD))

echo $DIFF

OFILE=/tmp/solar.email

EMAIL=solar_daily@rotwang.co.uk

echo "To: $EMAIL" > $OFILE
echo "Subject: yesterday's solar reading $DIFF" >> $OFILE
echo "" >> $OFILE
echo "$DIFF Wh" >> $OFILE

curl smtp://localhost:8825 --mail-from $EMAIL --mail-rcpt $EMAIL --upload-file $OFILE

# FIN
