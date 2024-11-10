#!/usr/bin/python
# -*- coding: UTF-8 -*-
#import chardet
import os
import sys 
import time
import logging
import spidev as SPI
import LCD_1inch69
from PIL import Image, ImageDraw, ImageFont
from mcp3002 import mcp3002
import pigpio

# Raspberry Pi pin configuration:
RST = 27
DC = 25
BL = 18
bus = 0 
device = 0 


# --------------------- ADC Setup ---------------------
VR_MAX = 3.3
VR_LOW = 30
VR_HIGH = 70

pi = pigpio.pi()
mcp3002 = mcp3002(pi, 1, 1000000, VR_MAX)

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
    draw.rectangle( erasebox, fill="WHITE" )
    draw.text( (25,120), str(i), fill="RED", font=normalFont )
    disp.ShowImage(image1.rotate(270))

    #v = mcp3002.get_value(0)
    #v2 = mcp3002.get_volt( v )
    #print( "Value:"+str(v2) )

    time.sleep(0.5)

disp.module_exit()
