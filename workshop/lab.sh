from machine import Pin
import neopixel

np = neopixel.NeoPixel(Pin(38), 8)

# update LED 1 to red 
np[0] = (32, 0, 0)

# update LED 3 to green
np[2] = (0, 32, 0)

# update LED 8 to blue
np[7] = (0, 0, 32)
30 so they aren't blindingly bright)
np[5] = (25, 5, 12)   # Pink
np[6] = (25, 0, 25)   # Fuchsia / Magenta
np[7] = (10, 0, 25)   # Purple


np.write()

