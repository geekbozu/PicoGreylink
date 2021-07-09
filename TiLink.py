import machine
import utime
import rp2
import micropython
import select
import sys

class TiLink:
    """
    Tx and Rx routines to speak to a Ti-8X calculator over 2 gpio pins on the raspberry pi pico
    Runs on PIO0 using statemachines 0-2, Uses all 32 bytes of instruction memory
    """
    PIO0_BASE = 0x50200000
    PIO_IRQ = 0x0030
    SM0_EXECCTRL = 0x00CC

    @rp2.asm_pio(out_init=(rp2.PIO.OUT_LOW,rp2.PIO.OUT_LOW),sideset_init=(rp2.PIO.OUT_LOW,rp2.PIO.OUT_LOW),
                set_init=(rp2.PIO.OUT_LOW,rp2.PIO.OUT_LOW),autopush=True,in_shiftdir=rp2.PIO.SHIFT_RIGHT,
                out_shiftdir=rp2.PIO.SHIFT_RIGHT,push_thresh=8,pull_thresh=8)
    def txrx(): 
        wrap_target()
        label('idleloop')
        mov(x,status) .side(0)      # 1  Status, set IF fifo has 0 elements, clear if 1 or more  Set Both lines to input/Hi
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
        #set(pindirs,2)              # 11 Assert white  Red = Input White = Low
        wait(0,pins,0) .side(2)             # 12 wait for red to be asserted
        jmp('bit_final_stage')      # 13 
        label('tx_0_bit')
        set(pindirs,1)              # 14 Assert red 
        wait(0,pins,1)              # 15 wait for white to be asserted
        label('bit_final_stage')    
        wait(1,pins,0) .side(0)     # 16 Free both lines, Wait for red to de-assert
        wait(1,pins,1)              # 17 wait for white to de-assert
        jmp(not_osre,'byteloop')    # 18 proceed to next bit, Or exit
        jmp('idleloop')             # 19 return to idle

        label('rxstart')   
        set(x,7)                    # 20 Bitcount -1
        label('innerrx')
        wait(0,irq, 2)              # 21 wait for irq to clear signaling we have a starting bit
        in_(pins,1)                 # 22 Save white line, Asserted = 0Bit, de-asserted = 1bit
        jmp(pin,'ifRed')            # 23 Check red, jump to appropriate ACK
        wait(1,pin,0) .side(2)      # 24 De-assert white, wait for red to go high
        jmp('endrx')                # 25
        label('ifRed')
        wait(1,pin,1)  .side(1)     # 26 De-Assert red, wait for white to go high
        label('endrx')
        set(pindirs,0)
        irq(2) #.side(0)             # 27 Clear Bit start IRQ
        jmp(x_dec,'innerrx')        # 28 Continue RX loop until bit count = 0
        irq(0)                      # 29 Assert rx irq
        jmp('idleloop')             # 30 back to top. 
    
    #Pin watch routine
    #will watch in_base for a low transition and signal to IRQ 0 of the event
    #For TiLink Routines this must have a nominally low execution frequency or the transfer will fail....
    @rp2.asm_pio()
    def pinwatch():        
        wrap_target()
        wait(0,pin,0)               # 31 wait for pin to go low
        irq(clear,2)                # 32 Assert IRQ 0
        wrap()

    def __init__(self,base):
        self.tip = base
        self.ring = base+1
        #setup pins
        self.red = machine.Pin(self.tip, machine.Pin.IN)
        self.white = machine.Pin(self.ring, machine.Pin.IN)

        self.txrxStateMachine = rp2.StateMachine(0,self.txrx,freq=500000,sideset_base=machine.Pin(self.tip),set_base=machine.Pin(self.tip), 
                    in_base=machine.Pin(self.tip),out_base=machine.Pin(self.tip),jmp_pin=machine.Pin(self.tip))
        self.redWatch= rp2.StateMachine(1,self.pinwatch,freq=500000,in_base=machine.Pin(self.tip))
        self.whiteWatch= rp2.StateMachine(2,self.pinwatch,freq=500000,in_base=machine.Pin(self.ring))
        machine.mem32[self.PIO0_BASE+self.SM0_EXECCTRL] += 0x20000001 

    def begin(self):
        self.txrxStateMachine.active(1)
        self.whiteWatch.active(1)
        self.redWatch.active(1)  

    def stop(self):
        self.txrxStateMachine.active(0)
        self.whiteWatch.active(0)
        self.redWatch.active(0)  

    def reset():
        self.txrxStateMachine.restart()
        self.whiteWatch.restart()
        self.redWatch.restart() 

    def get(self):
        return self.txrxStateMachine.get()>>24

    def put(self,data):
        self.txrxStateMachine.put(data)

    def irq(self,routine):
        self.txrxStateMachine.irq(routine)
        
        
    def rx_fifo(self):
        return self.txrxStateMachine.rx_fifo()
    
    def tx_fifo(self):
        return self.txrxStateMachine.tx_fifo()
    

