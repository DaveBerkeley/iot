
function on_pir()
    tx("wiki/iot.cgp?pir=1")
end

pir = 7 -- GPIO13
gpio.mode(pir, gpio.INPUT)
gpio.trig(pir, "down", on_pir)

