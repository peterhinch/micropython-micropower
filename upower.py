# upower.py Enables access to functions useful in low power Pyboard projects
# Copyright 2015 Peter Hinch
# V0.1 7th October 2015

# http://www.st.com/web/en/resource/technical/document/application_note/DM00025071.pdf
import pyb, stm, os, utime, uctypes

class RTCError(OSError):
    pass

def buildcheck(tupTarget):
    fail = True
    if 'uname' in dir(os):
        datestring = os.uname()[3]
        date = datestring.split(' on')[1]
        idate = tuple([int(x) for x in date.split('-')])
        fail = idate < tupTarget
    if fail:
        raise OSError('This driver requires a firmware build dated {:4d}-{:02d}-{:02d} or later'.format(*tupTarget))

buildcheck((2015,10,9)) # Bug in earlier versions made lpdelay() unpredictable, also issue with standby > 5 mins.

@micropython.asm_thumb
def ctz(r0):                                    # Count the trailing zeros in an integer
    rbit(r0, r0)
    clz(r0, r0)

class BkpRAM(object):
    BKPSRAM = 0x40024000
    def __init__(self):
      stm.mem32[stm.RCC + stm.RCC_APB1ENR] |= 0x10000000 # PWREN bit
      stm.mem32[stm.PWR + stm.PWR_CR] |= 0x100 # Set the DBP bit in the PWR power control register
      stm.mem32[stm.RCC +stm.RCC_AHB1ENR]|= 0x40000 # enable BKPSRAMEN
      stm.mem32[stm.PWR + stm.PWR_CSR] |= 0x200 # BRE backup register enable bit
    def __getitem__(self, idx):
        assert idx >= 0 and idx <= 0x3ff, "Index must be between 0 and 1023"
        return stm.mem32[self.BKPSRAM + idx * 4]
    def __setitem__(self, idx, val):
        assert idx >= 0 and idx <= 0x3ff, "Index must be between 0 and 1023"
        stm.mem32[self.BKPSRAM + idx * 4] = val
    def get_bytearray(self):
        return uctypes.bytearray_at(self.BKPSRAM, 4096)

bkpram = BkpRAM()

class RTC_Regs(object):
    def __getitem__(self, idx):
        assert idx >= 0 and idx <= 19, "Index must be between 0 and 19"
        return stm.mem32[stm.RTC + stm.RTC_BKP0R+ idx * 4]
    def __setitem__(self, idx, val):
        assert idx >= 0 and idx <= 19, "Index must be between 0 and 19"
        stm.mem32[stm.RTC + stm.RTC_BKP0R + idx * 4] = val

rtcregs = RTC_Regs()
rtcregs[0] = 0x32f2

rtc = pyb.RTC()

def lpdelay(ms, usb_connected = False):         # Low power delay. Note stop() kills USB
    if usb_connected:
        pyb.delay(ms)
        return
    rtc.wakeup(ms)
    pyb.stop()
    rtc.wakeup(None)

class Tamper(object):
    def __init__(self):
        self.edge_triggered = False
        self.triggerlevel = 0
        self.tampmask = 0
        self.disable()                          # Ensure no events occur until we're ready
        self.pin = pyb.Pin.board.X18
        self.pin_configured = False             # Conserve power: enable pullup only if needed
        self.setup()

    def setup(self, level = 0, *, freq = 16, samples = 2, edge = False):
        self.tampmask = 0
        if level == 1:
            self.tampmask |= 2
            self.triggerlevel = 1
        elif level == 0:
            self.triggerlevel = 0
        else:
            raise ValueError("level must be 0 or 1")
        if type(edge) == bool:
            self.edge_triggered = edge
        else:
            raise ValueError("edge must be True or False")
        if not self.edge_triggered:
            if freq in (1,2,4,8,16,32,64,128):
                self.tampmask |= ctz(freq) << 8
            else:
                raise ValueError("Frequency must be 1, 2, 4, 8, 16, 32, 64 or 128Hz")
            if samples in (2, 4, 8):
                self.tampmask |= ctz(samples) << 11
            else:
                raise ValueError("Number of samples must be 2, 4, or 8")

    def _pinconfig(self):
        if not self.pin_configured:
            self.pin.init(mode = pyb.Pin.IN, pull = pyb.Pin.PULL_UP)
            self.pin_configured = True

    def disable(self):
        stm.mem32[stm.RTC + stm.RTC_TAFCR] = self.tampmask

    def wait_inactive(self, usb_connected = False):
        self._pinconfig()
        while self.pin.value() == self.triggerlevel: # Wait for pin to go logically off
            lpdelay(50, usb_connected)

    @property
    def pinvalue(self):
        self._pinconfig()
        return self.pin.value()

    def enable(self):
        BIT21 = 1 << 21                                 # Tamper mask bit
        self.disable()
        stm.mem32[stm.EXTI + stm.EXTI_IMR] |= BIT21     # Set up ext interrupt
        stm.mem32[stm.EXTI + stm.EXTI_RTSR] |= BIT21    # Rising edge
        stm.mem32[stm.EXTI + stm.EXTI_PR] |= BIT21      # Clear pending bit

        stm.mem32[stm.RTC + stm.RTC_ISR] &= 0xdfff      # Clear tamp1f flag
        stm.mem32[stm.PWR + stm.PWR_CR] |= 2            # Clear power wakeup flag WUF
        stm.mem32[stm.RTC + stm.RTC_TAFCR] = self.tampmask | 5 # Tamper interrupt enable and tamper1 enable

tamper = Tamper()

class wakeup_X1(object):                                # Support wakeup on low-high edge on pin X1
    def __init__(self):
        self.disable()
        self.pin = pyb.Pin.board.X1                     # Don't configure pin unless user accesses wkup
        self.pin_configured = False

    def _pinconfig(self):
        if not self.pin_configured:
            self.pin.init(mode = pyb.Pin.IN, pull = pyb.Pin.PULL_DOWN)
            self.pin_configured = True

    def enable(self):                                   # In this mode pin has pulldown enabled
        stm.mem32[stm.PWR + stm.PWR_CR] |= 4            # set CWUF to clear WUF in PWR_CSR
        stm.mem32[stm.PWR + stm.PWR_CSR] |= 0x100       # Enable wakeup

    def disable(self):
        stm.mem32[stm.PWR + stm.PWR_CSR] &= 0xfffffeff  # Disable wakeup

    def wait_inactive(self, usb_connected = False):
        self._pinconfig()
        while self.pin.value() == 1:                    # Wait for pin to go low
            lpdelay(50, usb_connected)

    @property
    def pinvalue(self):
        self._pinconfig()
        return self.pin.value()

wkup = wakeup_X1()

# Return the reason for a wakeup event. Note that boot detection uses the last word of backup RAM.
def why():
    if bkpram[1023] != 0x27288a6f:
        bkpram[1023] = 0x27288a6f
        return 'BOOT'
    rtc_isr = stm.mem32[stm.RTC + stm.RTC_ISR]
    if rtc_isr & 0x2000 == 0x2000:
        return 'TAMPER'
    if rtc_isr & 0x400 == 0x400:
        return 'WAKEUP'
    return 'X1'

def now():  # Return the current time from the RTC in secs and millisecs from year 2000
    secs = utime.time()
    ms = 1000*(255 -rtc.datetime()[7]) >> 8
    if ms < 50:                                 # Might have just rolled over
        secs = utime.time()
    return secs, ms

# Save the current time in mS 
def savetime(addr = 1021):
    bkpram[addr], bkpram[addr +1] = now()

# Return the number of mS outstanding from a delay of delta mS
def ms_left(delta, addr = 1021):
    if bkpram[1023] != 0x27288a6f:
        raise RTCError("System not initialised.")
    if not (bkpram[addr +1] <= 1000 and bkpram[addr +1] >= 0):
        raise RTCError("Time data not saved.")
    start_ms = 1000*bkpram[addr] + bkpram[addr +1]
    now_secs, now_millis = now()
    now_ms = 1000* now_secs + now_millis
    result = max(start_ms + delta - now_ms, 0)
    if result > delta:
        raise RTCError("Invalid saved time data.")
    return result

def ms_set(): # For debug purposes only. Decodes outcome of setting rtc.wakeup().
    dividers = (16, 8, 4, 2)
    wucksel = stm.mem32[stm.RTC + stm.RTC_CR] & 7
    div = dividers[wucksel & 3]
    wut = stm.mem32[stm.RTC + stm.RTC_WUTR] & 0xffff
    clock_period = div/32768 if wucksel < 4 else 1.0  # seconds
    period = clock_period * wut if wucksel < 6 else clock_period * (wut + 0x10000)
    return 1000 * period
