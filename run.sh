#!/bin/bash

CMD=watch.py

xpid=$(ps aux | grep $CMD | grep -v grep | grep -v vim | tr -s " " | cut "-d " -f 2)
echo "killing" $xpid
kill $xpid

./$CMD -s 1>&2 >/tmp/watch.log &

# FIN
