#!usr/bin/env python
# -*- coding: utf-8 -*-

import smbus
import time
import serial

bus = smbus.SMBus(1)

def atp3012(cmd):
	cmd0 = ord(cmd[0])
	cmd1 = []
	for c in cmd[1:]:
		cmd1.append(ord(c))

	print( "CMD0:",cmd0 )
	print( "CMD1:",cmd1 )

	bus.write_i2c_block_data(0x2e, cmd0, cmd1)   # コマンド送信実行

def atp3013(cmd):
	print("start")
	str = []
	for c in cmd:
		str.append(ord(c))
	
	for s in [str[i:i+30] for i in range(0,len(str), 30)]:
		print( s )
		bus.write_i2c_block_data(0x2e, 4, s)   # コマンド送信実行

	time.sleep(0.2*len(cmd))
	return

	time.sleep(2)

	# 喋り終わるまで待機（かなり怪しいけど）
	while True:
		r = [1]
		try:
			r = bus.read_i2c_block_data(0x2e, 0, 6)
			print( r )
		except:
			print("end")
			time.sleep(2)
			return
		time.sleep(0.3)

def atp3014(message ):
    uart=serial.Serial('/dev/ttyS0', 9600, timeout=10)
    uart.write(bytes(message+"\r\n","ascii"))


cmd = ""

import sys

if( len(sys.argv)!=2 ):
	print( "python3 [talk phrase]" )
	exit
else:
	atp3014( sys.argv[1]+"\r" )

