import cv2
import numpy as np
import sys


def checkWasher(image, template, max_zoom, accuracy):

	img = cv2.imread(image)
	tpl = cv2.imread(template)

	for i in range(100,max_zoom+1,10):
		#print(f"IMG:{image} / TPL:{template} / ZOOM:{i}")

		# テンプレートの拡大
		tpl2 = cv2.resize(tpl, None, fx=i/100, fy=i/100,interpolation=cv2.INTER_CUBIC)

		# マルチマッチ
		result = cv2.matchTemplate(img, tpl2, cv2.TM_CCOEFF_NORMED)
		print( cv2.minMaxLoc(result) )

		ys, xs = np.where(result >= accuracy)

		if len(ys):
	#		dst = img.copy()
	#		for x, y in zip(xs, ys):
	#			cv2.rectangle(dst,(x, y),(x+tpl2.shape[1], y+tpl2.shape[0]),color=(0, 255, 0),thickness=2)

			#cv2.imshow("frame", dst)
			#cv2.waitKey(0)
			return True, i
	
	return False, 0
	
	cv2.waitKey(0)
	cv2.destroyAllWindows()

#---

if( len(sys.argv)!=2 ):
	print( "python3 program [test file]" )
	exit
else:

	#タイマーセットしていないチェック
	res, zoom = checkWasher( sys.argv[1], "light_off_template.png", 100, 0.95 )
	if res:
		print(f"Timer is OFF")
		sys.exit()

	sys.exit()



	#タイマーセット済みのチェック
	res, zoom = checkWasher( sys.argv[1], "light_4h_template.png", 100, 0.85 )
	if res:
		print(f"Timer(4h) is ON!")
		sys.exit()
	res, zoom = checkWasher( sys.argv[1], "light_2h_template.png", 100, 0.85 )
	if res:
		print(f"Timer(2h) is ON!")
		sys.exit()
	

	
	res,zoom = checkWasher( sys.argv[1], "light_off_template.png", 200, 0.95 )
	if res:
		print( f"Door is open&off (zoom={zoom})" )
		sys.exit()

	res,zoom = checkWasher( sys.argv[1], "light_4h_template.png", 200, 0.78 )
	if res:
		print( f"Door is open & on(4h) (zoom={zoom})" )
		sys.exit()

	res,zoom = checkWasher( sys.argv[1], "light_2h_template.png", 200, 0.70 )
	if res:
		print( f"Door is open & on(2h) (zoom={zoom})" )
		sys.exit()


