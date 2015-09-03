# micropython-micropower
Some ideas for building ultra low power systems based on the Pyboard

These notes describe some general points in achieving minimum power draw from Pyboard based systems. A
circuit design and PCB layout are offered for achieving this when the Pyboard is used with external chips
or modules; it was specifically designed for the e-paper display and the NRF24L01 radio, but it could
readily be used with other devices. Some calculations are presented suggesting limits to the runtimes
that might be achieved from various types of batteries.

## Use cases

I have considered two types of use case. The first is a monitoring application which periodically wakes,
reads some data from a sensor then returns to standby. At intervals it uses an NRF24L01 radio to send the
accumulated data to a remote host. The second is a remote display using the NRF24L01 to acquire data from
a remote host and an e-paper display to enable this to be presented when the Pyboard is in standby. In
either case the Pyboard might be battery powered or powered from a power constrained source such as solar
photovoltaic cells.

## Standby mode

To achieve minimum power the code must be deigned so that the Pyboard spends the majority of its time in
standby mode. In this mode the current drawn by the MPU drops to some 4uA. The Pyboard draws about
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

 # code to run every time goes here
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
even when the latter is powered down. There are two obvious solutions. The first is to switch Vdd as in the
above schematic (single-ended mode) and also to provide switches in series with the relevant GPIO pins. The second is to
switch both Vdd and Vss of the connected hardware (double-ended mode). I prefer the single ended approach.
The current consumed by the connected hardware when the Pyboard is in standby is then negligible compared to
the total current draw of 29uA. This (from datasheet values) comprises 4uA for the microprocessor and 25uA
for the LDO regulator.

This can be reduced further by disabling or removing the LDO regulator: I have measured 7uA offering the
possibility of a year's operation from a CR2032 button cell. In practice achieving this is dependent on the
frequency and duration of power up events.

## Design details

The following design provides for single ended switching as described above and also - by virtue of a PCB
design - simplifies the connection of the Pyboard to an e-paper display and the NRF24L01. Connections
are provided for other I2C devices namely ferroelectric RAM (FRAM) [modules](https://learn.adafruit.com/adafruit-i2c-fram-breakout)
and the BMP180 pressure sensor although these pins may readily be employed for other I2C modules.

The design uses two Pyboard pins to control the peripheral power and the pullup resistors. Separate control is
preferable because it enables devices to be powered off prior to disabling the pullups, which is
recommended for some peripherals. An analog switch is employed to disable the pullup resistors.

Resistors R3, R4 and capacitor C1 are optional and provide the facility for a switched filtered,
slew rate limited 3.3V output. This was initially provided for the FRAM modules which specify a minimum and maximum
slew rate: for these fit R3 and R4. In this instance C1 may be omitted as the modules have a 10uF capacitor
onboard.

![Schematic](epd_vddonly_schem.jpg)

An editable version is provided in the file epd_vddonly.fzz - this requires the free (as in beer) software
from [Fritzing](http://fritzing.org/home/) where PCB's can be ordered. I should add a caveat that
at the time of writing the circuit has been tested but the PCB layout has not.
 
## Driver

This is generalised to provide for the use of alternative hardware. If two pins are specified it assumes
that the active high pin controls the pullups and the active low one controls power as above. If a
single pin is specified it is assumed to control both.

```python
import pyb
class PowerController(object):
    def __init__(self, pin_active_high, pin_active_low):
        if pin_active_low is not None:    # Start with power down
            self.al = pyb.Pin(pin_active_low, mode = pyb.Pin.OUT_PP)
            self.al.high()
        else:
            self.al = None
        if pin_active_high is not None:   # and pullups disabled
            self.ah = pyb.Pin(pin_active_high, mode = pyb.Pin.OUT_PP)
            self.ah.low()
        else:
            self.ah = None

    def power_up(self):
        if self.ah is not None:
            self.ah.high()                # Enable I2C pullups
        if self.al is not None:
            self.al.low()                 # Power up
        pyb.delay(10)                     # Nominal time for device to settle

    def power_down(self):
        if self.al is not None:
            self.al.high()                # Power off
        pyb.delay(10)                     # Avoid glitches on I2C bus while power decays
        if self.ah is not None:
            self.ah.low()                 # Disable I2C pullups

    @property
    def single_ended(self):               # Pullups have separate control
        return (self.ah is not None) and (self.al is not None)
```

# Pyboard modification
 
For the very lowest power consumption the LDO regulator should be removed from the Pyboard. Doing this
will doubtless void your warranty and commits you to providing a 3.3V power supply even when connecting
to the Pyboard with USB. The regulator is the rectangular component with five leads located near the
X3 pins [here](http://micropython.org/static/resources/pybv10-pinout.jpg).

A more readily reversible alternative to removal is to lift pin 3 and link it to gnd.

# Some numbers
 
With the regulator removed the Pyboard consumes about 7uA. In a year of operation this corrsponds to
an energy utilisation of 61mAH, compared to the 225mAH nominal capacity of a CR2032 cell.
 
@moose measured the startup charge required by the Pyboard [here](http://forum.micropython.org/viewtopic.php?f=6&t=607).
This corresponds to about 9mAS or 0.0025mAH. If we start every ten minutes, annual consumption from
startup events is  
0.0025 x 6 x 24 x 365 = 131mAH. Adding the 61mAH from standby gives 192mAH, close to the
capacity of the cell. This sets an upper bound on the frequency of power up events to achieve the notional
one year runtime, although this could be doubled with an alternative button cell (see below).
 
A more computationally demanding test involved updating an epaper display with the following script
 
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

Modules epaper and micropower located [here](https://github.com/peterhinch/micropython-epaper.git).

This used an average of 85mA for 6S to do an update. If the script performed one refresh per hour this would equate
to  
85 x 6/3600 = 141uA average + 7uA quiescent = 148uA. This would exhaust a CR2032 in 9 weeks. An alternative is the
larger CR2450 button cell with 540mAH capacity which would provide 5 months running.

A year's running would be achievable if the circuit were powered from three AA alkaline cells - obviously the
regulator would be required in this instance:

Power = 141uA + 29uA quiescent = 170uA x 24 x 365 = 1.5AH which is within the nominal capacity of these cells.

# Pyboard enhancements

Micropower operation would be simpler if a future iteration of the Pyboard included the following,
controllable in user code:  
 1. A switched 3.3V peripheral power output.  
 2. A facility to disable the I2C pullups.  
 3. A facility to disable the regulator via its enable pin.
