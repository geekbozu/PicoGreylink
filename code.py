import machine
import utime
import rp2


@rp2.asm_pio(out_init=(rp2.PIO.OUT_HIGH,rp2.PIO.OUT_HIGH),set_init=(rp2.PIO.OUT_HIGH,rp2.PIO.OUT_HIGH),autopush=True,in_shiftdir=rp2.PIO.SHIFT_RIGHT)
def rx():
    wrap_target()
    label('start')
    set(pins,3)         #set both pins high
    irq(block, 0)       #wait until either pin goes low
    in_(pins,1)          #Puts current bit into isr
    jmp(pin,'ifRed')    #If red is low
    set(pins,1)         #set red low, NOTE this is a bit mask....
    wait(1,pin,0)      #wait for white to go high
    jmp('start')
    label('ifRed')
    set(pins,2)         #set white low, NOTE this is a bit mask....
    wait(1,pin,1)      #wait for white to go high
    wrap()

@rp2.asm_pio()
def pinwatch():
    wrap_target()
    wait(0,pin,0)
    irq(clear,0)
    wrap()





#setup pins
red = machine.Pin(0, machine.Pin.IN)
white = machine.Pin(1, machine.Pin.IN)
redOut = machine.Pin(2, machine.Pin.OUT)
whiteOut = machine.Pin(3, machine.Pin.OUT)


#In pin is 1, Because we care about the white line....
mainStateMachine = rp2.StateMachine(0, rx,freq=20000, set_base=machine.Pin(2), in_base=machine.Pin(0),out_base=machine.Pin(2),push_thresh=8,jmp_pin=machine.Pin(0) )
redWatchMachine = rp2.StateMachine(1, pinwatch, freq=2000,in_base=machine.Pin(0))
whiteWatchMachine = rp2.StateMachine(2, pinwatch, freq=2000,in_base=machine.Pin(1))
print("Starting state machines...")
mainStateMachine.active(1)
redWatchMachine.active(1)
whiteWatchMachine.active(1)


# Continually start and stop state machine
while True:    
    print(hex(sm.get()>>24))  ##Shift all bits >>24 because they are in MSB of teh input register


