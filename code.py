import machine
import utime
import rp2

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


# RX routine for TiLink protocol
#Assumse all data is sent in 8bit aligned incrememnts.
#will auto shift data to the RX Fifo upon RXing of 8bits
#bits will be stored in upper bits...31:23. Reading application will need to shift bits >>24 to correctly justify data
@rp2.asm_pio(out_init=(rp2.PIO.OUT_HIGH,rp2.PIO.OUT_HIGH),set_init=(rp2.PIO.OUT_HIGH,rp2.PIO.OUT_HIGH),autopush=True,in_shiftdir=rp2.PIO.SHIFT_RIGHT,push_thresh=8)
def rx():               #10 Instructions
    wrap_target()
    label('rxstart')
    set(pins,3)         #set both pins high/End/Readyup for next bit
    wait(0,irq,1)       # wait for rx lock to go low
    irq(block, 0)       #wait for irq to clear signaling we are starting a bit
    in_(pins,1)         #Shift in White line...which holds our current valid bit.
    jmp(pin,'ifRed')    #If Red is high Jump to Red as Ack
    set(pins,1)         #Set White Line low to ACK
    wait(1,pin,0)      #wait for red to go high
    jmp('rxstart')
    label('ifRed')
    set(pins,2)         #Set Red Line low to ACK
    wait(1,pin,1)      #Wait for white to go high
    wrap()

@rp2.asm_pio(out_init=(rp2.PIO.OUT_HIGH,rp2.PIO.OUT_HIGH),sideset_init=(rp2.PIO.OUT_HIGH,rp2.PIO.OUT_HIGH),
            set_init=(rp2.PIO.OUT_HIGH,rp2.PIO.OUT_HIGH),autopush=True,in_shiftdir=rp2.PIO.SHIFT_RIGHT,
            out_shiftdir=rp2.PIO.SHIFT_RIGHT,push_thresh=8,pull_thresh=8)
def txrx(): 
    wrap_target()
    label('idleloop')
    mov(x,status)
    jmp(not_x,'txstart')
    set(y,0x3)   #bitmask for no bits pressed
    in_(pins,2)
    mov(x,reverse(isr))
    mov(isr,null)
    jmp(x_not_y,'rxstart')
    wrap()   # 7 
    
    label('txstart')
    pull()
    label('byteloop')    
    out(x,1)                 #Put LSB into x
    jmp(not_x,'tx_0_bit')    #bit is 0 then jump
    set(pins,1) 
    wait(0,pins,0)   #pull white low & wait for red to low
    jmp('bit_final_stage')   #jump to shared final wait
    label('tx_0_bit')
    set(pins,2) 
    wait(0,pins,1)  #pull red low & wait for white to low
    label('bit_final_stage')
    wait(1,pins,0) .side(3) 
    wait(1,pins,1)           #Wait for both lines to be deasserted
    jmp(not_osre,'byteloop')
    jmp('idleloop')          #13/20

    label('rxstart')   
    set(x,7)
    label('innerrx')
    #
    wait(0,irq, 0)            #wait for irq to clear signaling we are starting a bit
    #
    in_(pins,1)               #Shift in White line...which holds our current valid bit.
    jmp(pin,'ifRed')          #If Red is high Jump to Red as Ack
    wait(1,pin,0) .side(1)    #ack with white and wait for red to go high
    jmp('endrx')
    label('ifRed')
    wait(1,pin,1)  .side(2)   #Set Red Line low to ACK   #Wait for white to go high
    label('endrx')
    set(pins,3)
    irq(0)
    jmp(x_dec,'innerrx') 
    jmp('idleloop')
 
#Pin watch routine
#will watch in_base for a low transition and signal to IRQ 0 of the event
#For TiLink Routines this must have a nominally low execution frequency or the transfer will fail....
@rp2.asm_pio()
def pinwatch():         #2 Instructions
    wrap_target()
    wait(0,pin,0)     #wait for pin to go low
    irq(clear,0)       #Acknowledge IRQ 0
    wrap()


#setup pins
red = machine.Pin(0, machine.Pin.IN)
white = machine.Pin(1, machine.Pin.IN)
#setup pins
redOut = machine.Pin(2, machine.Pin.OUT,machine.Pin.PULL_UP)
whiteOut = machine.Pin(3, machine.Pin.OUT,machine.Pin.PULL_UP)

redOut.on()
whiteOut.on()
print("plug in Calculator")
#utime.sleep(5)
#In pin is 1, Because we care about the white line....

txrxStateMachine = rp2.StateMachine(0,txrx,freq=6000,sideset_base=machine.Pin(2),set_base=machine.Pin(2), 
                    in_base=machine.Pin(0),out_base=machine.Pin(2) )
redWatch= rp2.StateMachine(1,pinwatch,freq=6000,in_base=machine.Pin(0))
whiteWatch= rp2.StateMachine(2,pinwatch,freq=6000,in_base=machine.Pin(1))
machine.mem32[PIO0_BASE+SM0_EXECCTRL] += 1 
print("Starting state machines...")

txrxStateMachine.active(1)
whiteWatch.active(1)
redWatch.active(1)

RDY = [0x73, 0xA2, 0x0D , 0x00 , 0x00 , 0x00 , 0x019, 0x00 , 0x00 , 0x00 , 0x00 , 0x00 , 0x00 , 0x00 , 0x00 , 0x00 , 0x00 , 0x19,0x00]
for b in RDY:
   txrxStateMachine.put(b)

print("rxing")
# Continually start and stop state machine
while True:    
   print(hex(txrxStateMachine.get()>>24))   #Doesnt like 1 bits all the time it seems?
    
   
#txrxStateMachine.put(0x0F)
#txrxStateMachine.put(0x0F)
#txrxStateMachine.put(0x0F)

retrycount = 0

while True:
    val = ""
    if(txrxStateMachine.rx_fifo()):
        val = hex(txrxStateMachine.get()>>24)
    data = machine.mem32[PIO0_BASE+SM0_INSTR]
    addr = machine.mem32[PIO0_BASE+SM0_ADDR]
    exctrl = machine.mem32[PIO0_BASE+SM0_EXECCTRL]
    pictrl = machine.mem32[PIO0_BASE+SM0_PINCTRL]
    instr = decode_pio(data,(pictrl >> 26) & 7,True if exctrl & (1<<30) else False)
    print(" Instr, PC, execreg, retry"+str([instr,hex(addr),hex(exctrl),hex(retrycount),hex(data)]) + " rx " + str(txrxStateMachine.rx_fifo())+" " +val + " tx " + str(txrxStateMachine.tx_fifo()),end="\r")

    utime.sleep_ms(20)
   # txrxStateMachine.put(0xFF)
    retrycount += 1
    
    

 
print("rxing")
# Continually start and stop state machine
while True:    
   print(hex(rxStateMachine.get()>>24))   #Doesnt like 1 bits all the time it seems?
    


