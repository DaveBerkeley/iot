
function tx(req)
    conn=net.createConnection(net.TCP, false)
    conn:on("receive", function(conn, pl) print(pl) end)
    conn:connect(80,"192.168.0.56")
    conn:send("GET /" .. req .. " HTTP/1.1\r\nHost: esp8266\r\n\r\n")
end

function on_pir()
    tx("wiki/iot.cgp?pir=1")
end

pir = 7 -- GPIO13
gpio.mode(pir, gpio.INPUT)
gpio.trig(pir, "down", on_pir)

