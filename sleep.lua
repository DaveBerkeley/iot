
pir = 7     -- GPIO13
enable = 6  -- GPIO12
gpio.mode(pir, gpio.INPUT)
gpio.write(enable, gpio.LOW)
gpio.mode(enable, gpio.OUTPUT)

-- was the wakeup because of the PIR?
v = 1 - gpio.read(pir)

function tx(req)
    conn=net.createConnection(net.TCP, false)
    conn:on("receive", function(conn, pl) print("rxdata") end)
    conn:connect(80,"192.168.0.56")
    conn:send("GET /" .. req .. " HTTP/1.1\r\nHost: esp8266\r\n\r\n")
end

function on_pir(state)
    local v = adc.read(0)
    tx("wiki/iot.cgp?pir=" .. state .. "&adc=" .. v) 
end

function sleep()
    gpio.write(enable, gpio.HIGH)
    print("go to sleep, zzzzzzz")
    node.dsleep(10000000) 
end

function chain()
    local a = adc.read(0)
    tx("wiki/iot.cgp?pir=" .. v .. "&adc=" .. a) 
    -- TODO can go to sleep rapdily here
    tmr.alarm(0, 500, 0, function() sleep() end)
end

-- give it some time get the WiFi running
tmr.alarm(0, 3000, 0, function() chain() end)
-- print the function that would kill the timer
print('tmr.alarm(0, 1000, 0, function() print("x") end)')

