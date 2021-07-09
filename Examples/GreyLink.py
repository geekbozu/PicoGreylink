import micropython
import select
import sys
from TiLink import TiLink


print("starting")
ti = TiLink(0)
ti.begin()

micropython.kbd_intr(-1)

while True:
    while sys.stdin in select.select([sys.stdin], [], [], 0)[0]:        
        ch = sys.stdin.buffer.read(1)
        ti.put(ch)
    else:
        for i in range(ti.rx_fifo()):
            sys.stdout.buffer.write(bytes([ti.get()]))
