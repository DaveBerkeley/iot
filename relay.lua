
relay = 1
key = 3
on = false
gpio.mode(relay, gpio.OUTPUT)

function set(state)
    on = state
    if state == false then
        gpio.write(relay, gpio.LOW)
    else
        gpio.write(relay, gpio.HIGH)
    end
end

function on_msg(msg)
    print(msg)
    if msg == "on" then
        set(true)
    elseif msg == "off" then
        set(false)
    elseif msg == "toggle" then
        set(not on)
    end
end

-- Create a UDP listener
s = net.createServer(net.UDP) 
s:on("receive",function(conn, data) on_msg(data) end)
s:listen(5000)

set(false)


