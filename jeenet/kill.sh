#!/bin/bash

xpid=`ps aux | grep $1 | grep -v grep | grep -v vim | tr -s " " | cut "-d " -f 2`
echo "killing" $xpid
kill $xpid
