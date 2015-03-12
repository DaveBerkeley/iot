
relay = 1   -- GPIO05
relay_state = false
gpio.mode(relay, gpio.OUTPUT)

key = 3     -- GPIO03
gpio.mode(key, gpio.INPUT)

function set_relay(state)
    relay_state = state
    if state == false then
        gpio.write(relay, gpio.LOW)
    else
        gpio.write(relay, gpio.HIGH)
    end
end

function on_msg(msg)
    print(msg)
    if msg == "on" then
        return set_relay(true)
    end
    if msg == "off" then
        return set_relay(false)
    end
    if msg == "toggle" then
        return set_relay(not relay_state)
    end

    -- turn the relay on for x milliseconds?
    x, x, num = string.find(msg, "pulse=(%d+)")
    if num then
        set_relay(true)
        tmr.alarm(0, num, 0, function() set_relay(false) end)
    end
end

-- Create a UDP listener
s = net.createServer(net.UDP) 
s:on("receive",function(con, data) on_msg(data) end)
s:listen(5000)

set_relay(false)

function tx(req)
    conn=net.createConnection(net.TCP, false)
    conn:on("receive", function(conn, pl) print(pl) end)
    conn:connect(80,"192.168.0.56")
    conn:send("GET /" .. req .. " HTTP/1.1\r\nHost: esp8266\r\n\r\n")
end

function on_pir()
    tx("wiki/iot.cgp?pir=1")
end

gpio.trig(key, "down", on_pir)

