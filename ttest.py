# ttest.py Demonstrate ways to exit from pyb.standby()

# Copyright Peter Hinch 8 Nov 2015

# draws 32uA between LED flashes runing from flash.
# This doesn't do much running from USB because the low power modes kill the USB interface.
# Note that the blue LED is best avoided in these applications as it currently uses PWM: this can
# lead to some odd effects in time dependent applications.
# Note also that pyboard firmware briefly flashes the green LED on all wakeups.

import pyb, utime, upower
upower.tamper.setup(level = 0, freq = 16, samples = 2, edge = False) # A level of zero triggers
#upower.tamper.setup(level = 1, edge = True) # Falling edge trigger. You must supply a pullup resistor.

leds = tuple(pyb.LED(x) for x in range(1, 5))   # rgyb
for led in leds:
    led.off()

reason = upower.why()                           # Why have we woken?
if reason == 'BOOT':                            # first boot or reset: yellow LED
    if upower.bkpram[0] != 1:                  # never booted before
        upower.rtc.datetime((2015, 8, 6, 4, 13, 0, 0, 0))  # Code to run on 1st boot only
        upower.bkpram[0] = 1                   # we may have an RTC backup battery
        leds[1].on()
        leds[0].on()                            # RGY == 1st boot
    leds[2].on()                                # Y only == subsequent boots (with battery)
    upower.savetime()
elif reason == 'WAKEUP':                        # green and yellow on timer wakeup
    leds[1].on()
    leds[2].on()
    upower.savetime()
elif reason == 'TAMPER':                        # red
    leds[0].on()
elif reason == 'X1':                            # red and green on X1 rising edge
    leds[1].on()
    leds[0].on()

if not upower.usb_connected:                    # Assume boot.py has set up a UART
    t = upower.rtc.datetime()[4:7]
    print('{:02d}.{:02d}.{:02d}'.format(t[0],t[1],t[2]))

upower.lpdelay(500, upower.usb_connected)              # ensure LED visible before standby turns it off
upower.tamper.wait_inactive(upower.usb_connected)      # Wait for tamper signal to go away
upower.wkup.wait_inactive(upower.usb_connected)
upower.lpdelay(50, upower.usb_connected)               # Wait out any contact bounce
                                                # demo of not resetting the wakeup timer after a pin interrupt
try:                                            # ms_left can fail in response to various coding errors
    timeleft = upower.ms_left(10000)
except upower.RTCError:
    timeleft = 10000                            # Here we just restart the timer
timeleft = max(timeleft, 1000)                  # Set a minimum sleep duration: too short and it uses less power to stay awake
                                                # In real apps this might be longer or you might deal with it in other ways.
upower.rtc.wakeup(timeleft)
# These calls reconfigure hardware and should be done last, shortly before standby()
upower.tamper.enable()
upower.wkup.enable()
if not upower.usb_connected:
    pyb.standby()                               # This will set pins hi-z and turn LEDs off
