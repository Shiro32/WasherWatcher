#!/usr/bin/python
# -*- coding: UTF-8 -*-
#import chardet
import os
import sys 
import time
import spidev
import LCD_1inch69
from PIL import Image, ImageDraw, ImageFont
import pigpio

# Raspberry Pi pin configuration:
RST = 27
DC = 25
BL = 18
bus = 0 
device = 0 


# --------------------- ADC Setup ---------------------
spi = spidev.SpiDev()
spi.open(0, 1) # bus0, cs1
spi.max_speed_hz = 1000000


normalFont = ImageFont.truetype('Font.ttc', 40)

# display with hardware SPI:
''' Warning!!!Don't  creation of multiple displayer objects!!! '''
#disp = LCD_1inch69.LCD_1inch69(spi=SPI.SpiDev(bus, device),spi_freq=10000000,rst=RST,dc=DC,bl=BL)
disp = LCD_1inch69.LCD_1inch69()
disp.Init()
disp.clear()

# Create blank image for drawing.
image1 = Image.new("RGB", (disp.width,disp.height ), "WHITE")
draw = ImageDraw.Draw(image1)

i = 0
erasebox = draw.textbbox((25,120), "000", font=normalFont )

while True:
    i = i+1
    resp = spi.xfer2([0x68, 0x00])
    volume = ((resp[0]<<8)+resp[1])&0x3FF
    print( "Value:"+str(volume) )

    draw.rectangle( erasebox, fill="WHITE" )
    draw.text( (25,120), str(volume), fill="RED", font=normalFont )
    disp.ShowImage(image1.rotate(270))

    time.sleep(0.001)

disp.module_exit()
