import cv2
import numpy as np
from picamera2 import Picamera2
import sys

# 撮影写真のトリミング領域（実際のパターンマッチングに使うのは狭い領域なので）
WASHER_CAP_TRIM_TOP		= 1/6*3
WASHER_CAP_TRIM_BOTTOM	= 1/6*5

WASHER_CAP_TRIM_LEFT	= 1/6*2
WASHER_CAP_TRIM_RIGHT	= 1/6*4
# 食洗器撮影写真サイズ
CAPTURE_WIDTH	= 1280
CAPTURE_HEIGHT	= 960

MAIN_WIDTH = 240

# プレビューサイズ
PREVIEW_ASPECT	= CAPTURE_WIDTH/CAPTURE_HEIGHT	# アスペクトレシオ（プレビュー用）
PREVIEW_WIDTH	= MAIN_WIDTH
PREVIEW_HEIGHT	= int(PREVIEW_WIDTH/PREVIEW_ASPECT)

def _capture_washer()->np.ndarray:
	"""
	カメラモジュールで食洗器を撮影する
	（戻り値） トリミング加工された写真（np.ndarray）

	・フルサイズで撮影する
	・左右の真ん中、上下の下半分にトリミングする
	"""

	picam = Picamera2()
	picam.configure(
		picam.create_preview_configuration(
			main={"format": 'XRGB8888', "size": (CAPTURE_WIDTH, CAPTURE_HEIGHT)}))

	# 撮影
	picam.start()
	img = picam.capture_array()
	picam.stop()
	picam.close()

	# カラーモードの調整なのかな
	chs = 1 if len(img.shape)==2 else img.shape[2]
	if chs==1:
		img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
	if chs==4:
		img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

	# トリミング
	w = img.shape[1]
	h = img.shape[0]
	img = img[
		int(h*WASHER_CAP_TRIM_TOP) :int(h*WASHER_CAP_TRIM_BOTTOM),
		int(w*WASHER_CAP_TRIM_LEFT):int(w*WASHER_CAP_TRIM_RIGHT)] #top:bottom, left:right

	#cv2.imwrite( "shot.png", img )
	return img


def match(img, temp_file):

	img_g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

	tpl = cv2.imread( temp_file )
	tpl_g = cv2.cvtColor(tpl, cv2.COLOR_RGB2GRAY)

	print("read complete")
	#パターンマッチ
	result = cv2.matchTemplate(img_g, tpl_g, cv2.TM_CCOEFF_NORMED)

	#結果位置
	minVal, corr, minLoc, maxLoc = cv2.minMaxLoc(result)

	tl = maxLoc[0], maxLoc[1]
	br = maxLoc[0]+tpl.shape[1], maxLoc[1]+tpl.shape[0]

	# 4h
	tl4 = maxLoc[0]+22, maxLoc[1]+8
	br4 = tl4[0]+6, tl4[1]+6

	# 2h
	tl2 = maxLoc[0]+22, maxLoc[1]+14
	br2 = tl2[0]+6, tl2[1]+6

	box4 = img[ tl4[1]:br4[1], tl4[0]:br4[0] ]
	box2 = img[ tl2[1]:br2[1], tl2[0]:br2[0] ]

	print( f"CR:{corr:.3f}")

	print( "【R層】")
	c4 = box4.T[2].flatten().mean()
	c2 = box2.T[2].flatten().mean()
	print( f"4H:{c4:.0f} / 2H:{c2:.0f} / R:{max(c2,c4)/min(c2,c4):.2f}")

	print( "【B層】")
	c4 = box4.T[0].flatten().mean()
	c2 = box2.T[0].flatten().mean()
	print( f"4H:{c4:.0f} / 2H:{c2:.0f} / R:{max(c2,c4)/min(c2,c4):.2f}")

	print( "【G層】")
	c4 = box4.T[1].flatten().mean()
	c2 = box2.T[1].flatten().mean()
	print( f"4H:{c4:.0f} / 2H:{c2:.0f} / R:{max(c2,c4)/min(c2,c4):.2f}")

	print("【R+G】")
	c4 = box4.T[1].flatten().mean()*0.5 + box4.T[2].flatten().mean()
	c2 = box2.T[1].flatten().mean()*0.5 + box2.T[2].flatten().mean()	
	print( f"4H:{c4:.0f} / 2H:{c2:.0f} / R:{max(c2,c4)/min(c2,c4):.2f}")

	# 方法２：全画素平均値（黒よりは明るいだろう）
	print("\n【輝度（合計）】")
	c4 = box4.T[0].flatten().mean() + box4.T[1].flatten().mean() + box4.T[2].flatten().mean()
	c2 = box2.T[0].flatten().mean() + box2.T[1].flatten().mean() + box2.T[2].flatten().mean()	
	print( f"4H:{c4:.0f} / 2H:{c2:.0f} / R:{max(c2,c4)/min(c2,c4):.2f}")

	# 方法３：HSV
	print("\n【HSV】")
	img_HSV = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
	box4 = img_HSV[ tl4[1]:br4[1], tl4[0]:br4[0] ]
	box2 = img_HSV[ tl2[1]:br2[1], tl2[0]:br2[0] ]

	c4 = box4.T[0].flatten().mean()
	c2 = box2.T[0].flatten().mean()
	print( f"H 4H:{c4:.0f} / 2H:{c2:.0f} / R:{max(c2,c4)/min(c2,c4):.2f}")
	c4 = box4.T[1].flatten().mean()
	c2 = box2.T[1].flatten().mean()
	print( f"S 4H:{c4:.0f} / 2H:{c2:.0f} / R:{max(c2,c4)/min(c2,c4):.2f}")
	c4 = box4.T[2].flatten().mean()
	c2 = box2.T[2].flatten().mean()
	print( f"V 4H:{c4:.0f} / 2H:{c2:.0f} / R:{max(c2,c4)/min(c2,c4):.2f}")



	# 全体マッチ
	cv2.rectangle(img, tl, br, color=(0,255,0), thickness=1)
	cv2.rectangle(img, tl4, br4, color=(255,0,0),thickness=1)
	cv2.rectangle(img, tl2, br2, color=(255,0,0),thickness=1)


	cv2.imwrite("result.png", img)

if( len(sys.argv)==2 ):
	img = cv2.imread( sys.argv[1] )
else:
	img = _capture_washer()

match(img, "../pattern/3buttons_light_close.png")

