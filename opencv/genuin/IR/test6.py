#!usr/bin/env python
# -*- coding: utf-8 -*-

import cv2
import numpy as np
import sys
import pprint

from picamera2 import Picamera2

def checkWasher(image, template, max_zoom ):

	img = cv2.cvtColor( image, cv2.COLOR_RGB2GRAY )
	tpl = cv2.cvtColor( cv2.imread(template), cv2.COLOR_RGB2GRAY )

	if max_zoom==00:
		result = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
		_, corr, _, _ = cv2.minMaxLoc(result)

		return corr, 100

	else:

		corr = 0
		zoom = 100

		for i in range(100, max_zoom+1 , 1):

			# テンプレートの拡大
			tpl2 = cv2.resize(tpl, None, fx=i/100, fy=i/100,interpolation=cv2.INTER_CUBIC)

			result = cv2.matchTemplate(img, tpl2, cv2.TM_CCOEFF_NORMED)
			_, v, _, _ = cv2.minMaxLoc(result)

			if v>corr:
				corr = v
				zoom = i

		return corr, zoom

#---

if( len(sys.argv)!=2 ):
	picam2  = Picamera2()
	picam2.configure(picam2.create_preview_configuration(main={"format": 'XRGB8888', "size": (1280, 960)    }))
	picam2.start()

	img = picam2.capture_array()
	chs = 1 if len(img.shape)==2 else img.shape[2]
	if chs==1:
		img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
	if chs==4:
		img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

	#cv2.imshow("IN:", img)
	#while True:
	#	key = cv2.waitKey(1)
	#	# Escキーを入力されたら画面を閉じる
	#	if key == 27: break


else:
	img = cv2.imread( sys.argv[1] )

#タイマーセットしていないチェック

#img = img[700:959, 0:1279]

results=[]

#corr, zoom = checkWasher( img, "dark_off_template.png", 100)
#results.append( {"STATUS":"CLOSE & OFF", "ZOOM":zoom, "CORR":corr} )
corr, zoom = checkWasher( img, "dark_off_template.png", 130)
results.append( {"STATUS":"OPEN  & OFF", "ZOOM":zoom, "CORR":corr} )

#corr, zoom = checkWasher( img, "dark_2h_template.png", 100)
#results.append( {"STATUS":"CLOSE & 2H ", "ZOOM":zoom, "CORR":corr} )
corr, zoom = checkWasher( img, "dark_2h_template.png", 130)
results.append( {"STATUS":"OPEN  & 2H ", "ZOOM":zoom, "CORR":corr} )

#corr, zoom = checkWasher( img, "dark_4h_template.png", 100)
#results.append( {"STATUS":"CLOSE & 4H ", "ZOOM":zoom, "CORR":corr} )
corr, zoom = checkWasher( img, "dark_4h_template.png", 130)
results.append( {"STATUS":"OPEN  & 4H ", "ZOOM":zoom, "CORR":corr} )


results = sorted(results, key=lambda x:x["CORR"], reverse=True)
#print("RESULTs")
#pprint.pprint( results )


for x in results:
	status = x["STATUS"]
	corr = x["CORR"]
	zoom = x["ZOOM"]

	print( f"{status} / {corr:.3f} / {zoom}")

#	print( f"STATUS:{x["STATUS"]}")


if "picam2" in locals():
	picam2.stop()


#print( f"CLOSE-OFF:{corr:.3f}")

