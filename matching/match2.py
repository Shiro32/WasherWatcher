import cv2
import numpy as np
from picamera2 import Picamera2

TEMP_CASTELLI_OPEN = "./pattern/castelli_open.png"
TEMP_CASTELLI_CLOSE = "./pattern/castelli_close.png"

# 明るい・ドア閉
TEMP_LIGHT_CLOSE_OFF= "./pattern/icon_light_close_off.png"	# 予約なし
TEMP_LIGHT_CLOSE_2H	= "./pattern/icon_light_close_2h.png"	# ２ｈ予約
TEMP_LIGHT_CLOSE_4H	= "./pattern/icon_light_close_4h.png"	# ４ｈ予約

# 明るい・ドア開
TEMP_LIGHT_OPEN_OFF	= "./pattern/icon_light_open_off.png"	# 予約なし
TEMP_LIGHT_OPEN_2H	= "./pattern/icon_light_open_2h.png"	# ２ｈ予約
TEMP_LIGHT_OPEN_4H	= "./pattern/icon_light_open_4h.png"	# ４ｈ予約


# 撮影写真のトリミング領域（実際のパターンマッチングに使うのは狭い領域なので）
WASHER_CAP_TRIM_TOP		= 1/4*1
WASHER_CAP_TRIM_BOTTOM	= 1/4*4

WASHER_CAP_TRIM_LEFT	= 1/4*1
WASHER_CAP_TRIM_RIGHT	= 1/4*3
# 食洗器撮影写真サイズ
CAPTURE_WIDTH	= 2592
CAPTURE_HEIGHT	= 1944

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
	picam.start()

	# 撮影
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


def match():

	img = _capture_washer()
	img_g = cv2.cvtColor( img, cv2.COLOR_RGB2GRAY )

	print("開始！")

	# OPEN/CLOSE
	# close
	img_cl = cv2.imread( TEMP_CASTELLI_CLOSE )
	img_cl = cv2.cvtColor( img_cl, cv2.COLOR_RGB2GRAY )
	result = cv2.matchTemplate(img_g, img_cl, cv2.TM_CCOEFF_NORMED)
	_, corr_cl, _, maxLoc_cl = cv2.minMaxLoc(result)

	#open
	img_op = cv2.imread( TEMP_CASTELLI_OPEN )
	img_op = cv2.cvtColor( img_op, cv2.COLOR_RGB2GRAY )
	result = cv2.matchTemplate(img_g, img_op, cv2.TM_CCOEFF_NORMED)
	_, corr_op, _, maxLoc_op = cv2.minMaxLoc(result)

	print( f"CLOSE:{corr_cl} / OPEN:{corr_op}" )

	# CLOSE!
	if corr_cl>=corr_op:
		print( "CLOSE" )

		# 2H
		timer2h_tl = maxLoc_cl[0]+img_cl.shape[1]	, maxLoc_cl[1]+20
		timer2h_br = timer2h_tl[0]+12				, timer2h_tl[1]+12

		# 4H
		timer4h_tl = maxLoc_cl[0]+img_cl.shape[1]	, maxLoc_cl[1]+8
		timer4h_br = timer4h_tl[0]+12				, timer4h_tl[1]+12
	
	# OPEN!
	else:
		print( "OPEN" )

		# 2H
		timer2h_tl = maxLoc_op[0]+img_op.shape[1]	, maxLoc_op[1]+27
		timer2h_br = timer2h_tl[0]+13				, timer2h_tl[1]+12

		# 4H
		timer4h_tl = maxLoc_op[0]+img_op.shape[1]	, maxLoc_op[1]+10
		timer4h_br = timer4h_tl[0]+13				, timer4h_tl[1]+13

	print( timer2h_tl )
	print( timer2h_br )

	box2 = img[ timer2h_tl[1]:timer2h_br[1], timer2h_tl[0]:timer2h_br[0] ]
	box4 = img[ timer4h_tl[1]:timer4h_br[1], timer4h_tl[0]:timer4h_br[0] ]

	c2 = box2.T[2].flatten().mean()
	c4 = box4.T[2].flatten().mean()

	print( f"2H:{c2} / 4H:{c4}")

match()

