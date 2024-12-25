import cv2
import numpy as np
from picamera2 import Picamera2


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

	cv2.imwrite( "shot.png", img )
	return img


def match(temp_file):

	img = _capture_washer()
	tpl = cv2.imread( temp_file )

	print("read complete")
	#パターンマッチ
	result = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)

	#結果位置
	minVal, corr, minLoc, maxLoc = cv2.minMaxLoc(result)

	tl = maxLoc[0], maxLoc[1]
	br = maxLoc[0]+tpl.shape[1], maxLoc[1]+tpl.shape[0]

	dst = img.copy()

	# 全体マッチ
	cv2.rectangle(dst, tl, br, color=(0,255,0), thickness=1)

	# 4h
	tl3 = maxLoc[0]+30, maxLoc[1]+8
	br3 = tl3[0]+6, tl3[1]+6
	cv2.rectangle(dst, tl3, br3, color=(255,0,0),thickness=1)

	# 2h
	tl2 = maxLoc[0]+30, maxLoc[1]+16
	br2 = tl2[0]+6, tl2[1]+6
	cv2.rectangle(dst, tl2, br2, color=(255,0,0),thickness=1)

	box2 = dst[ tl2[1]:br2[1], tl2[0]:br2[0] ]
	box4 = dst[ tl3[1]:br3[1], tl3[0]:br3[0] ]

	print( f"CR:{corr:.3f}")
	print( f"2H:{box2.T[2].flatten().mean():.0f}")
	print( f"4H:{box4.T[2].flatten().mean():.0f}")

	cv2.imwrite("result.png", dst)


print("open")
match("./pattern/3buttons_dark_open.png" )
#print("close")
#match( "./pattern/castelli_light_close_small.png" )

