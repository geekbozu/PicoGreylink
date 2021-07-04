import machine
import utime
import rp2

# RX routine for TiLink protocol
#Assumse all data is sent in 8bit aligned incrememnts.
#will auto shift data to the RX Fifo upon RXing of 8bits
#bits will be stored in upper bits...31:23. Reading application will need to shift bits >>24 to correctly justify data
@rp2.asm_pio(out_init=(rp2.PIO.OUT_HIGH,rp2.PIO.OUT_HIGH),set_init=(rp2.PIO.OUT_HIGH,rp2.PIO.OUT_HIGH),autopush=True,in_shiftdir=rp2.PIO.SHIFT_RIGHT)
def rx():
    wrap_target()
    label('start')
    set(pins,3)         #set both pins high/End/Readyup for next bit
    irq(block, 0)       #wait for irq to clear signaling we are starting a bit
    in_(pins,1)         #Shift in White line...which holds our current valid bit.
    jmp(pin,'ifRed')    #If Red is high Jump to Red as Ack
    set(pins,1)         #Set White Line low to ACK
    wait(1,pin,0)       #wait for white to go high
    jmp('start')
    label('ifRed')
    set(pins,2)         #Set Red Line low to ACK
    wait(1,pin,1)       #Wait for white to go high
    wrap()              #back to top...


#Pin watch routine
#will watch in_base for a low transition and signal to IRQ 0 of the event
#For TiLink Routines this must have a nominally low execution frequency or the transfer will fail....
@rp2.asm_pio()
def pinwatch():
    wrap_target()
    wait(0,pin,0)      #wait for pin to go low
    irq(clear,0)       #Acknowledge IRQ 0
    wrap()





#setup pins
red = machine.Pin(0, machine.Pin.IN)
white = machine.Pin(1, machine.Pin.IN)
redOut = machine.Pin(2, machine.Pin.OUT)
whiteOut = machine.Pin(3, machine.Pin.OUT)


#In pin is 1, Because we care about the white line....
mainStateMachine = rp2.StateMachine(0, rx,freq=20000, set_base=machine.Pin(2), in_base=machine.Pin(0),out_base=machine.Pin(2),push_thresh=8,jmp_pin=machine.Pin(0) )
redWatchMachine = rp2.StateMachine(1, pinwatch, freq=20000,in_base=machine.Pin(0))
whiteWatchMachine = rp2.StateMachine(2, pinwatch, freq=20000,in_base=machine.Pin(1))
print("Starting state machines...")
mainStateMachine.active(1)
redWatchMachine.active(1)
whiteWatchMachine.active(1)


# Continually start and stop state machine
while True:    
    print(hex(sm.get()>>24))  ##Shift all bits >>24 because they are in MSB of teh input register


