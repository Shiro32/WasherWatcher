#!usr/bin/env python
# -*- coding: utf-8 -*-

from bottle import route, run, template, request
import smbus, time, serial

def atp3014(message ):
    uart=serial.Serial('/dev/ttyS0', 9600, timeout=10)
    uart.write(bytes(message+"\r\n","ascii"))

@route("/", method="GET")
@route("/")
def top_query():
	# idは半角英数字のみ
	str1 = request.query.get("text")

	if (str1 is not None) and (str1!=""):
		print( "STR:"+str(str1) )
		atp3014( str1+"\r" )

	return template('./remote.html')
 
if __name__ == '__main__':
	run( host='0.0.0.0',port=80,reloader=True,debug=True)
