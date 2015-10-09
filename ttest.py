# ttest.py Demonstrate ways to exit from pyb.standby()

# Copyright Peter Hinch 8th October 2015

# draws 32uA between LED flashes runing from flash.
# This doesn't do much running from USB because the low power modes kill the USB interface.
# Note that the blue LED is best avoided in these applications as it currently uses PWM: this can
# lead to some odd effects in time dependent applications.
# Note also that pyboard firmware briefly flashes the green LED on all wakeups.

import pyb, stm
from upower import rtc, tamper, why, lpdelay, wkup
tamper.setup(level = 0, freq = 16, samples = 2, edge = False) # A level of zero triggers
#tamper.setup(level = 1, edge = True) # Falling edge trigger. You must supply a pullup resistor.

leds = tuple(pyb.LED(x) for x in range(1, 5))   # rgyb
for led in leds:
    led.off()

usb_connected = pyb.Pin.board.USB_VBUS.value() == 1
if not usb_connected:
    pyb.usb_mode(None) # Save power

reason = why()                                  # Why have we woken?
if reason == 'BOOT':                            # first boot or reset: yellow LED
    rtc.datetime((2015, 8, 6, 4, 13, 0, 0, 0))  # Code to run on 1st boot only
    leds[2].on()
elif reason == 'TAMPER':                        # red
    leds[0].on()
elif reason == 'WAKEUP':                        # green and yellow on timer wakeup
    leds[1].on()
    leds[2].on()
elif reason == 'X1':                            # red and green on X1 rising edge
    leds[1].on()
    leds[0].on()

lpdelay(500, usb_connected)                     # ensure LED visible before standby turns it off
tamper.wait_inactive(usb_connected)             # Wait for tamper signal to go away
wkup.wait_inactive(usb_connected)
lpdelay(50, usb_connected)                      # Wait out any contact bounce
# These calls reconfigure hardware and should be done last, shortly before standby()
rtc.wakeup(10000)
tamper.enable()
wkup.enable()
if not usb_connected:
    pyb.standby()
