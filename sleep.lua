
relay = 1  -- GPIO05
enable = 6 -- GPIO12
gpio.mode(relay, gpio.OUTPUT)
gpio.write(relay, gpio.HIGH)

gpio.write(enable, gpio.LOW)
gpio.mode(enable, gpio.OUTPUT)

print('tmr.alarm(0, 1000, 0, function() print("none") end)')

function tx(req)
    print(req)
    conn=net.createConnection(net.TCP, false)
    conn:on("receive", function(conn, pl) print(pl) end)
    conn:connect(80,"192.168.0.56")
    conn:send("GET /" .. req .. " HTTP/1.1\r\nHost: esp8266\r\n\r\n")
end

function sleep()
    gpio.write(enable, gpio.HIGH)
    -- go to sleep, zzzzzzz
    node.dsleep(10000000) 
end

function chain()
    tx("wiki/iot.cgp?wake=1") 
    tmr.alarm(0, 10000, 0, function() sleep() end)
end

-- give it some time get the WiFi running
tmr.alarm(0, 3000, 0, function() chain() end)


