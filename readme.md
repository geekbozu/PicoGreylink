

# RP Pico TI Calculator Linking Library

A set of PIO state machine programs and routines for linking the PICO to a Ti-8X graphing calculator

### Routines. 
TBD, No Api has been solidfied yet

### Examples
This repository plans to include a python set of routines, and a C set of routines. Examples for both as well as an implementation of a silverlink emulator for use sending programs to and from a calculator via a PC.

### Hardware

The Pico is connected to a graphing calculator using 4 pins and 2 diodes to emulate an open collector bus. This could be done with fast switching of pins from input to output mode, However I find the code was easier and cleaner to write this way...for now. 

<img src="docs\BasicWireup.png" alt="BasicWireup" style="zoom:50%;" />

### Protocol 

Quoted from the [Ti Link Protocol Guide by Tim Singer And Romain Liévin](http://merthsoft.com/linkguide/index.html)

"The link port normally operates in a half-duplex mode where a bit is sent by activating the corresponding line ("ring" or "tip") and the receiver acknowledges by activating the other line. The sender now releases its line and finally the receiver releases the acknowledge. "

<img src="docs\protocol.png" alt="protocol" />

Above is an example of sending a 0xC9, Data is shifted out LSB first.

<img src="docs\get_chart.png" alt="get_chart"/> <img src="docs\put_chart.png" alt="put_chart"/>


These are a flow chart example of the send/rx logic



#### Thanks And Credits

Some of the Images used are curtesy of The TI Link Protocol Guide. 

Special thanks to

- Iambian  
- KermMartian and [Articl](https://github.com/KermMartian/ArTICL)
- BaldEngineer

