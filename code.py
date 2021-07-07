import machine
import utime
import rp2
import micropython
import select
import sys
PIO0_BASE = 0x50200000
PIO_IRQ = 0x0030
SM0_EXECCTRL = 0x00CC
SM0_PINCTRL = 0x00DC
SM0_ADDR = 0x00D4
SM0_INSTR = 0x00D8
SM1_EXECCTRL = 0x00E4
SM1_PINCTRL = 0x00F4
SM1_ADDR = 0x00EC
SM1_INSTR = 0x00F0
ATOMIC_NORMAL = 0x0000
ATOMIC_XOR = 0x1000
ATOMIC_OR = 0x02000
ATOMIC_AND = 0x3000

def decode_pio(uint16_val, sideset_bits = 0, sideset_opt = False):
    def decode_index(five_bit_value):
        s = str(five_bit_value & 7)
        if five_bit_value & 16:
            s += " REL"
        return s
    instr = (uint16_val >> 13) & 7
    delay_field = (uint16_val >> 8) & 31
    sidesetting = False
    if sideset_bits:
        bitting = sideset_bits + sideset_opt
        delay = delay_field & ((1 << (5-bitting)) - 1)
        if sideset_opt:
            if delay_field & 16:
                delay_field &= 15   #Clear sideset opt bit so the shift below...
                sidesetting = True
        else:
            sidesetting = True
        sideset = delay_field >> (5-bitting) #... does not contribute to the value
    else:
        sideset = 0
        delay = delay_field
    other = uint16_val & 255
    pushpullsel = (other >> 7) & 1
    output = ""
    if instr == 0:
        cond = (other >> 5) & 7
        output += "jmp "
        output += ["","!X ","X-- ","!Y ","Y-- ","X!=Y ","PIN ","!OSRE "][cond]
        output += hex(other&31)
    elif instr == 1:
        source = (other >> 5) & 3
        polarity = (other >> 7) & 1
        index = other & 31
        output += "wait " + str(polarity) + " " #encode polarity
        output += ["GPIO ","PIN ","IRQ ","<<ILLEGALSRC>>"][source]
        if source != 2:
            output += str(index)
        else:
            output += decode_index(index)
    elif instr == 2:
        source = (other >> 5) & 7
        bitcount = other & 31
        output += "IN "
        output += ["PINS ","X ","Y ","NULL ","<<ILLEGALSRC>>","<<ILLEGALSRC>>","ISR "," OSR "][source]
        output += str(bitcount)
    elif instr == 3:
        destination = (other >> 5) & 7
        bitcount = other & 31
        output += "OUT "
        output += ["PINS ","X ","Y ","NULL ","PINDIRS ","PC ","ISR "," EXEC "][destination]
        output += str(bitcount)
    elif (instr == 4) and (pushpullsel == 0):
        iffull = (other >> 6) & 1
        block  = (other >> 5) & 1
        output += "PUSH "
        output += ["","IFFULL "][iffull]
        output += ["NOBLOCK","BLOCK"][block]
    elif (instr == 4) and (pushpullsel == 1):
        ifempty = (other >> 6) & 1
        block  = (other >> 5) & 1
        output += "PULL "
        output += ["","IFEMPTY "][ifempty]
        output += ["NOBLOCK","BLOCK"][block]
    elif instr == 5:
        destination = (other >> 5) & 7
        oper = (other >> 3) & 3
        source = other & 7
        output += "MOV "
        output += ["PINS ","X ","Y ","<<ILLEGALDEST>>","EXEC ","PC ","ISR ","OSR "][destination]
        output += ["","~","::","<<ILLEGALOP>>"][oper]
        output += ["PINS","X","Y","NULL","<<ILLEGALSRC>>","STATUS","ISR","OSR"][source]
    elif instr == 6:
        clear = (other >> 6) & 1
        wait = (other >> 5) & 1 if clear == 0 else 0
        index = other & 31
        output += "IRQ "
        output += [" ","WAIT "][wait]
        output += [" ","CLEAR "][clear]
        output += decode_index(index)
    elif instr == 7:
        destination = (other >> 5) & 7
        data = other & 31
        si = "<<ILLEGALDAT>> "
        output += "SET "
        output += ["PINS ","X ","Y ",si,"PINDIRS ",si,si,si][destination]
        output += str(data)
    else:
        output = "NODECODE"
    #
    if sidesetting:
        output += " SIDE "+str(sideset)
    if delay:
        output += " ["+str(delay)+"]"
    return output



@rp2.asm_pio(out_init=(rp2.PIO.OUT_HIGH,rp2.PIO.OUT_HIGH),sideset_init=(rp2.PIO.OUT_HIGH,rp2.PIO.OUT_HIGH),
            set_init=(rp2.PIO.OUT_HIGH,rp2.PIO.OUT_HIGH),autopush=True,in_shiftdir=rp2.PIO.SHIFT_RIGHT,
            out_shiftdir=rp2.PIO.SHIFT_RIGHT,push_thresh=8,pull_thresh=8)
def txrx(): 
    wrap_target()
    label('idleloop')
    mov(x,status)               # 1  Status, set IF fifo has 0 elements, clear if 1 or more
    jmp(not_x,'txstart')        # 2  If status is clear, we have data to transmit
    set(y,0x3)                  # 3  bitmask for no bits pressed
    in_(pins,2)                 # 4  Read 2 input bits
    mov(x,reverse(isr))         # 5  Move bits, Reverse to account for Right Shift, We want bits in LSB
    mov(isr,null)               # 6  Clear ISR rest Autopull
    jmp(x_not_y,'rxstart')      # 7  if any line is low jump to RX
    wrap()                      #    End idle loop
    
    label('txstart')            #    Begin TX Routine
    pull()                      # 8  Get data into osr
    label('byteloop')    
    out(x,1)                    # 9  Put LSB into x
    jmp(not_x,'tx_0_bit')       # 10 bit is 0 then jump
    set(pins,1)                 # 11 Assert white
    wait(0,pins,0)              # 12 wait for red to be asserted
    jmp('bit_final_stage')      # 13 
    label('tx_0_bit')
    set(pins,2)                 # 14 Assert red 
    wait(0,pins,1)              # 15 wait for white to be asserted
    label('bit_final_stage')    
    wait(1,pins,0) .side(3)     # 16 Free both lines, Wait for red to de-assert
    wait(1,pins,1)              # 17 wait for white to de-assert
    jmp(not_osre,'byteloop')    # 18 proceed to next bit, Or exit
    jmp('idleloop')             # 19 return to idle

    label('rxstart')   
    set(x,7)                    # 20 Bitcount -1
    label('innerrx')
    wait(0,irq, 0)              # 21 wait for irq to clear signaling we have a starting bit
    in_(pins,1)                 # 22 Save white line, Asserted = 0Bit, de-asserted = 1bit
    jmp(pin,'ifRed')            # 23 Check red, jump to appropriate ACK
    wait(1,pin,0) .side(1)      # 24 De-assert white, wait for red to go high
    jmp('endrx')                # 25
    label('ifRed')
    wait(1,pin,1)  .side(2)     # 26 De-Assert red, wait for white to go high
    label('endrx')
    set(pins,3)                 # 27 De-assert both lines
    irq(0)                      # 28 Clear Bit start IRQ
    jmp(x_dec,'innerrx')        # 29 Continue RX loop until bit count = 0
    jmp('idleloop')             # 30 back to top. 
 
#Pin watch routine
#will watch in_base for a low transition and signal to IRQ 0 of the event
#For TiLink Routines this must have a nominally low execution frequency or the transfer will fail....
@rp2.asm_pio()
def pinwatch():        
    wrap_target()
    wait(0,pin,0)               # 31 wait for pin to go low
    irq(clear,0)                # 32 Assert IRQ 0
    wrap()



#setup pins
red = machine.Pin(0, machine.Pin.IN)
white = machine.Pin(1, machine.Pin.IN)
#setup pins
redOut = machine.Pin(2, machine.Pin.OUT,machine.Pin.PULL_UP)
whiteOut = machine.Pin(3, machine.Pin.OUT,machine.Pin.PULL_UP)

redOut.on()
whiteOut.on()

txrxStateMachine = rp2.StateMachine(0,txrx,freq=650000,sideset_base=machine.Pin(2),set_base=machine.Pin(2), 
                    in_base=machine.Pin(0),out_base=machine.Pin(2),jmp_pin=machine.Pin(0))
redWatch= rp2.StateMachine(1,pinwatch,freq=650000,in_base=machine.Pin(0))
whiteWatch= rp2.StateMachine(2,pinwatch,freq=650000,in_base=machine.Pin(1))
machine.mem32[PIO0_BASE+SM0_EXECCTRL] += 1 

txrxStateMachine.active(1)
whiteWatch.active(1)
redWatch.active(1)

micropython.kbd_intr(-1)
while True:
    while sys.stdin in select.select([sys.stdin], [], [], 0)[0]:        
        ch = sys.stdin.buffer.read(1)
        txrxStateMachine.put(ch)
    else:
        while (txrxStateMachine.rx_fifo()):
            sys.stdout.buffer.write(bytes([txrxStateMachine.get()>>24]))
