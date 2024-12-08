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
	minVal, maxVal, minLoc, maxLoc = cv2.minMaxLoc(result)

	tl = maxLoc[0], maxLoc[1]
	br = maxLoc[0]+tpl.shape[1], maxLoc[1]+tpl.shape[0]

	dst = img.copy()
	cv2.rectangle(dst, tl, br, color=(0,255,0), thickness=1)

	# 2h
	tl2 = maxLoc[0]+tpl.shape[1], maxLoc[1]+20
	br2 = tl2[0]+12, tl2[1]+12
	cv2.rectangle(dst, tl2, br2, color=(255,0,0),thickness=1)

	# 4h
	tl3 = maxLoc[0]+tpl.shape[1], maxLoc[1]+2+6
	br3 = tl3[0]+12, tl3[1]+12
	cv2.rectangle(dst, tl3, br3, color=(255,0,0),thickness=1)


	box2 = dst[ tl2[1]:br2[1], tl2[0]:br2[0] ]
	box4 = dst[ tl3[1]:br3[1], tl3[0]:br3[0] ]


	print( f"2H:{box2.T[2].flatten().mean()}")
	print( f"4H:{box4.T[2].flatten().mean()}")

	cv2.imwrite("result.png", dst)
	#cv2.imshow("frame", dst)

	#cv2.waitKey(0)
	#cv2.destroyAllWindows()


#print("open")
#match( TEMP_CASTELLI_OPEN )
print("close")
match( TEMP_CASTELLI_CLOSE )

