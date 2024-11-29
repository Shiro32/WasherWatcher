#!usr/bin/env python
# -*- coding: utf-8 -*-

# 食洗器監視のモジュール
# ラズパイカメラで読み取った写真を、OpenCVのパターンマッチングで判定
#
# ステータスは２つ
# 1.汚れた食器の有無（あり・なし）
# 2.ドアの状況（開・閉）
# 3.予約状況（予約済み・なし）
#
# ■履歴
# 2024/11/27 新規作成

import time
import datetime
import cv2
import numpy as np
from picamera2 import Picamera2
from typing import Tuple

from cfg import *   # 定数関係
import globals as g # グローバル変数・関数

# --------------------- washer内のグローバル変数 ---------------------

# 食洗器の状態
washer_dirty_dishes	= False
washer_door			= WASHER_DOOR_CLOSE
washer_timer		= WASHER_TIMER_OFF

# ------------------------------------------------------------------------------
def capture_washer()->np.ndarray:
	g.log( "WASHER","写真撮影")

	picam = Picamera2()
	picam.configure(
		picam.create_preview_configuration(
			main={"format": 'XRGB8888', "size": (640, 480)    }))
#			main={"format": 'XRGB8888', "size": (2592, 1944)    }))

	# 撮影
	picam.start()
	img = picam.capture_array()
	picam.stop()

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

	g.log( "WASHER","写真撮影完了")
	return img

# ------------------------------------------------------------------------------
def pattern_matching(image, template, max_zoom)->Tuple[float, float]:
	"""
	現在の食洗器の写真と、テンプレートを照合して一致度を計算する

	・現在の食洗器の中に、与えられたテンプレートが含まれている相関係数を計算
	・max_zoomが100より大きければ、その比率まで拡大してみて計算する

	引数：
		image	: 現在の食洗器の写真
		template: 予約ランプあたりのパターン写真
		max_zoom: 最大の拡大率

	戻り値：（x,y）
		x : 相関係数
		y : 拡大率
	"""
	img = cv2.cvtColor( image, cv2.COLOR_RGB2GRAY )
	tpl = cv2.cvtColor( cv2.imread(template), cv2.COLOR_RGB2GRAY )

	# 拡大を許さないパターン
	if max_zoom==00:
		result = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
		_, corr, _, _ = cv2.minMaxLoc(result)

		return corr, 100

	# 拡大を許すパターン（ドアを開けている状態を想定）
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

# ------------------------------------------------------------------------------
def check_washer_now()->None:
	"""
	食洗器を撮影して、現在の状況を確認する
	あくまでも現状を見るだけで、過去の経緯（食器有無、洗浄済みなど）はかかわらない

	戻り値：(int x, int y)
	　x : ドアの状態（open/close）
	　y : タイマの状態（off/2h/4h/now）
	"""
	g.log( "WASHER","食洗器チェック")

	img = capture_washer()

	results = []

	corr, zoom = pattern_matching( img, "./pattern/light_off_template.png", 130)
	results.append( {"STATUS":"OPEN  & OFF", "ZOOM":zoom, "CORR":corr} )

	corr, zoom = pattern_matching( img, "./pattern/light_2h_template.png", 130)
	results.append( {"STATUS":"OPEN  & 2H ", "ZOOM":zoom, "CORR":corr} )

	corr, zoom = pattern_matching( img, "./pattern/light_4h_template.png", 130)
	results.append( {"STATUS":"OPEN  & 4H ", "ZOOM":zoom, "CORR":corr} )

	#結果整理
	results = sorted(results, key=lambda x:x["CORR"], reverse=True)

	for x in results:
		status = x["STATUS"]
		corr = x["CORR"]
		zoom = x["ZOOM"]

		print( f"{status} / {corr:.3f} / {zoom}")

	return WASHER_DOOR_CLOSE, WASHER_TIMER_OFF
