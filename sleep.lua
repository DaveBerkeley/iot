
relay = 1
gpio.mode(relay, gpio.OUTPUT)
gpio.write(relay, gpio.HIGH)

print('tmr.alarm(0, 1000, 0, function() print("none") end)')

tmr.alarm(0, 10000, 0, function() node.dsleep(10000000) end)

