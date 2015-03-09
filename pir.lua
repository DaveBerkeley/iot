
relay = 1
on = false
gpio.mode(relay, gpio.OUTPUT)

function set_relay(state)
    on = state
    if state == false then
        gpio.write(relay, gpio.LOW)
    else
        gpio.write(relay, gpio.HIGH)
    end
end

function tx(req)
    conn=net.createConnection(net.TCP, false)
    conn:on("receive", function(conn, pl) print(pl) end)
    conn:connect(80,"192.168.0.56")
    conn:send("GET /" .. req .. " HTTP/1.1\r\nHost: esp8266\r\n\r\n")
end

--[[
key = 3
gpio.mode(key, gpio.INPUT)
gpio.mode(key, gpio.INT)
gpio.trig(key, "down", function() tx("key") end)
]]

set_relay(false)

function on_pir()
    set_relay(true)
    tmr.alarm(0, 2000, function() set_relay(false) end)
    tx("wiki/pir.cgp")
end

pir = 5
gpio.mode(pir, gpio.INPUT)
gpio.trig(pir, "down", on_pir)

