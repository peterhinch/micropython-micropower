# alarm.py Demonstrate using RTC alarms to exit pyb.standby()

# Copyright Peter Hinch
# V0.3 18th February 2016
# Flashes red on boot, then flashes red and green and red and amber LED's alternately
# at 30 second intervals courtesy of two concurrent timers
# (each times out at one minute intervals).
import stm, pyb, upower

led = pyb.LED(1)
led.on()                                        # Red every time
rtc = pyb.RTC()
reason = upower.why()                           # Why have we woken?
if reason == 'BOOT':                            # first boot or reset: yellow LED
    rtc.datetime((2015, 8, 6, 4, 13, 0, 0, 0))  # Code to run on 1st boot only
    aa = upower.Alarm('a')
    aa.timeset(second = 39)
    ab = upower.Alarm('b')
    ab.timeset(second = 9)
elif reason == 'ALARM_A':
    lg = pyb.LED(2)
    lg.on()
elif reason == 'ALARM_B':
    ly = pyb.LED(3)
    ly.on()

pyb.delay(1000)     # Let LED's be seen!
pyb.standby()
