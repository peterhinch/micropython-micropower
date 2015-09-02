# micropython-micropower
Some ideas for building ultra low power systems based on the Pyboard

These notes describe some general points in achieving minimum power draw from Pyboard based systems. A
circuit design and PCB layout are offered for achieving this when the Pyboard is used with external chips
or modules; it was specifically designed for the e-paper display and the NRF24L01 radio, but it could
readily be used with other devices.

When in standby mode the current drawn by the MPU drops to some 4uA. The Pyboard as a whole draws typically
30uA largely owing to the onboard LDO voltage regulator which cannot (without surgery) be disabled. A
typical application will use code along these lines:

```python
import pyb, stm
rtc = pyb.RTC()

usb_connected = pyb.Pin.board.USB_VBUS.value() == 1
if not usb_connected:
   pyb.usb_mode(None) # Save power

if stm.mem32[stm.RTC + stm.RTC_BKP1R] == 0:     # first boot
   rtc.datetime((2015, 8, 6, 4, 13, 0, 0, 0))   # Code to run on 1st boot only

 # code to run every time
rtc.wakeup(20000)
stm.mem32[stm.RTC + stm.RTC_BKP1R] = 1 # indicate that we are going into standby mode
if not usb_connected:
   pyb.standby()
```

The ``usb_connected`` logic simplifies debugging using a USB cable while minimising power when run without USB. The
first boot detection is a potentially useful convenience.

# Hardware issues

Most practical applications will have hardware peripherals connected to Pyboard GPIO pins and the
various Pyboard interfaces. To conserve power these should be powered down when the Pyboard is in standby,
and the Pyboard provides no means of doing this. In principle this could be achieved thus:

![Schematic](simple_schem.jpg)

On first boot or on leaving standby the code drives the pin low, then drives it high before entering standby.
In this state the GPIO pins go high impedance, so the MOSFET remains off by virtue of the resistor.

Unfortunately this is inadequate for devices using the I2C bus or using its pins as GPIO. This is because
the Pyboard has pullup resistors on these pins which will source current into the connected hardware
even when the latter is powered down. There are two possible solutions. The first is to provide switches in
series with the relevant GPIO pins. The second is to switch both Vdd and Vss of the connected hardware. I
have adopted the former approach. The current consumed by the connected hardware when the Pyboard is in
standby is then negligible compared to the total current draw of 29uA. This (from datasheet values) comprises
4uA for the microprocessor and 25uA for the LDO regulator.

This can be reduced further by disabling or removing the LDO regulator: I have measured 7uA offering the
possibility of a year's operation from a CR2032 button cell. In practice achieving this is dependent on the
frequency and duration of power up events.

# Design details

This uses two Pyboard pins to control the peripheral power and the pullup resistors. Separate control is
best because it enables devices to be powered off prior to disabling the pullups, which is
preferable for some peripherals. An analog switch is employed to disable the pullup resistors.

Resistors R3, R4 and capacitor C1 are optional and provide the facility for a switched filtered,
slew rate limited 3.3V output. This was initially provided for ferroelectric RAM (FRAM)
[modules](https://learn.adafruit.com/adafruit-i2c-fram-breakout) which specify a minimum and maximum
slew rate: for these fit R3 and R4. In this instance C1 may be omitted as the modules have a 10uF capacitor
onboard.

![Schematic](epd_vddonly_schem.jpg)

An editable version, with a PCB designed to simplify connectivity to the epaper display and other
devices including the NRF24L01 radio, is provided in the file epd_vddonly.fzz - this requires the free
(as in beer) software from [Fritzing](http://fritzing.org/home/) where copies of the PCB can be ordered.
 
# Pyboard modification
 
For the very lowest power consumption the LDO regulator should be removed from the Pyboard. Doing this
will doubtless void your warranty and commits you to providing a 3.3V power supply even when connecting
to the Pyboard with USB. The regulator is the rectangular component with five leads located near the
X3 pins [here](http://micropython.org/static/resources/pybv10-pinout.jpg).
 
# Some numbers
 
With the regulator removed the Pyboard consumes about 7uA. In a year of operation this corrsponds to
an energy utilisation of 61mAH, compared to the 225mAH nominal capacity of a CR2032 cell.
 
@moose measured the startup charge required by the Pyboard [here](http://forum.micropython.org/viewtopic.php?f=6&t=607).
This corresponds to about 9mAS or 0.0025mAH. If we start every ten minutes, annual consumption from
startup events is 0.0025*6*24*365 = 131mAH. Added to the 61mAH from standby gives 192mAH, close to the
capacity of the cell. This sets an upper bound on the frequency of power up events for the notional one
year runtime.
 
A more heavy duty test involved updating an epaper display with the following script
 
```python
import pyb, epaper, stm
from micropower import PowerController
rtc = pyb.RTC()

usb_connected = pyb.Pin.board.USB_VBUS.value() == 1
if not usb_connected:
    pyb.usb_mode(None) # Save power

if stm.mem32[stm.RTC + stm.RTC_BKP1R] == 0:     # first boot
    rtc.datetime((2015, 8, 6, 4, 13, 0, 0, 0)) # Arbitrary

t = rtc.datetime()[4:7]
timestring = '{:02d}.{:02d}.{:02d}'.format(t[0],t[1],t[2])
p = PowerController(pin_active_high = 'Y12', pin_active_low = 'Y11')
a = epaper.Display(side = 'Y', use_flash = True, pwr_controller = p)
s = str(a.temperature) + "C\n" + timestring
a.mountflash() # Power up
with a.font('/fc/LiberationSerif-Regular45x44'):
    a.puts(s)
a.umountflash() # Keep filesystem happy
a.show()

rtc.wakeup(20000)
stm.mem32[stm.RTC + stm.RTC_BKP1R] = 1 # indicate that we are going into standby mode
if usb_connected:
    p.power_up()                        # Power up for testing
else:
    pyb.standby()
```

Modules from [here](https://github.com/peterhinch/micropython-epaper.git).

This used an average of 85mA for 6S to do an update. If the script performed one refresh per hour this would equate
to 85*6/3600 = 141uA average + 7uA quiescent = 148uA. This would exhaust a CR2032 in 9 weeks. However a year's
running would be achievable if the circuit were powered from three AA alkaline cells - obviously the regulator would be
retained in this instance.

Power = 141uA + 29uA quiescent = 170uA * 24 * 365 = 1.5AH which is within the nominal capacity of these cells.

# Pyboard enhancements

It would be good if a future iteration of the Pyboard included the following, controllable in user code:  
 1. A switched 3.3V peripheral power output.  
 2. A facility to disable the I2C pullups.  
 3. A facility to disable the regulator via its enable pin.

