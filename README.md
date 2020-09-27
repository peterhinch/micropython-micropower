# Reducing Pyboard system power consumption

This repository is specific to STM systems. It primarily supports Pyboard 1.x
and Pyboard D.

The Pyboard can be used to build systems with extremely low power consumption,
and it is possible to build systems capable of running for over a year on
standard batteries such as AA cells or even coin cells. With the Pyboard 1.x
series, achieving the lowest possible power consumption where peripheral
devices are attached requires a little additional hardware. The Pyboard D
overcomes this requirement by virtue of a software switchable 3.3V regulator
which also powers the I2C pullups.

Broadly there are two approaches, depending on the acceptable level of power
consumption. If an idle current in the range of 500uA to 1mA is acceptable,
code can be largely conventional with `pyb.stop()` being employed to reduce
power consumption during periods when the Pyboard is idle.

For the lowest possible power consumption `pyb.standby()` must be used, cutting
consumption to around 6μA. With external hardware on the Pyboard 1.x or via the
switchable regulator on the D series the peripherals may be turned off ensuring
that the entire system uses only this amount. The drawback of `standby` is that
on waking the Pyboard restarts as if from a reboot. This introduces potential
difficulties regarding determining the source of the wakeup and the storage of
program state while sleeping.

Two sets of resources are provided to assist with the development of low power
solutions.

### Hardware

[hardware](./HARDWARE.md) A discussion of techniques to minimise power
consumption including ways to shut down attached devices, calculation of
battery usage and measurements of results. A schematic for a typical system is
provided with accompanying PCB layout. 

### Software

[upower](./UPOWER.md) This documents `upower.py`, a module providing access to
features of the Pyboard SOC which are currently unsupported in the official
firmware. Some of these features may be of wider use, such as using the battery
backed RAM to store arbitrary Python objects and accessing the RTC registers.

All code is issued under the [MIT license](./LICENSE)
