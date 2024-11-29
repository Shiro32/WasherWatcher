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

# --------------------- washer内の定数 ---------------------
# テンプレート写真
TEMP_LIGHT_OFF	= "./pattern/light_off_template.png"	# 予約なし
TEMP_LIGHT_2H	= "./pattern/light_2h_template.png"	# ２ｈ予約
TEMP_LIGHT_4H	= "./pattern/light_4h_template.png"	# ４ｈ予約

# テンプレートとマッチングの最低閾値
TEMP_MATCHING_THRESHOULD = 0.90

# 食洗器撮影写真サイズ
CAPTURE_WIDTH	= 2592
CAPTURE_HEIGHT	= 1944
CAPTURE_ASPECT	= CAPTURE_WIDTH/CAPTURE_HEIGHT	# アスペクトレシオ1.3くらい

# プレビューサイズ
PREVIEW_WIDTH	= MAIN_WIDTH
PREVIEW_HEIGHT	= int(PREVIEW_WIDTH/CAPTURE_ASPECT)

# 撮影写真のトリミング領域（実際のパターンマッチングに使うのは狭い領域なので）
WASHER_CAP_TRIM_TOP		= 1/2*1
WASHER_CAP_TRIM_BOTTOM	= 1/2*2

WASHER_CAP_TRIM_LEFT	= 1/4*1
WASHER_CAP_TRIM_RIGHT	= 1/4*3

# --------------------- washer内のグローバル変数 ---------------------

# 食洗器の状態（状態を保持し続けるためにグローバル化）
# 暗くなる or 子機から問われた時はこれをもとに回答
washer_dirty_dishes	= False
washer_door			= WASHER_DOOR_CLOSE
washer_timer		= WASHER_TIMER_OFF

# ------------------------------------------------------------------------------
def capture_washer()->np.ndarray:
	"""
	カメラモジュールで食洗器を撮影する
	（戻り値） トリミング加工された写真（np.ndarray）

	・フルサイズで撮影する
	・左右の真ん中、上下の下半分にトリミングする
	"""

	g.log( "WASHER","写真撮影")

	picam = Picamera2()
	picam.configure(
		picam.create_preview_configuration(
			main={"format": 'XRGB8888', "size": (CAPTURE_WIDTH, CAPTURE_HEIGHT)}))

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

	# 写真を撮影
	img = capture_washer()

	# 3パターン（オフ、2H、4H）でパターンマッチングして、一番スコアの高いものを採用
	results = [] # {ドア状態、タイマー状態、相関値}

	# タイマー０
	corr, zoom = pattern_matching( img, TEMP_LIGHT_OFF, 130)
	results.append( {"DOOR":WASHER_DOOR_CLOSE if zoom==100 else WASHER_DOOR_OPEN, "TIMER":WASHER_TIMER_OFF, "CORR":corr} )
	# タイマー2H
	corr, zoom = pattern_matching( img, TEMP_LIGHT_2H, 130)
	results.append( {"DOOR":WASHER_DOOR_CLOSE if zoom==100 else WASHER_DOOR_OPEN, "TIMER":WASHER_TIMER_2H, "CORR":corr} )
	# タイマー4H
	corr, zoom = pattern_matching( img, TEMP_LIGHT_4H, 130)
	results.append( {"DOOR":WASHER_DOOR_CLOSE if zoom==100 else WASHER_DOOR_OPEN, "TIMER":WASHER_TIMER_4H, "CORR":corr} )

	#昇順ソート
	results = sorted(results, key=lambda x:x["CORR"], reverse=True)

	for x in results:
		door = x["DOOR"]
		timer = x["TIMER"]
		corr = x["CORR"]

		g.log( "WASHER", f"DOOR:{door} / TIMER:{timer} / {corr:.3f} / {zoom}" )

	# 一致度が最低ラインを下回っていたら、素直に「分からない」と回答
	if results[0]["CORR"] < TEMP_MATCHING_THRESHOULD:
		g.log("WASHER","判定できず")
		return WASHER_STATUS_UNKNOWN, WASHER_STATUS_UNKNOWN

	# 一致が見つかっているならそれを返す
	else:
		g.log("WASHER", f"発見！（DOOR:{results[0]['DOOR']}/TIMER{results[0]['TIMER']}）")
		return results[0]["DOOR"], results[0]["TIMER"]

# ------------------------------------------------------------------------------
def preview_washser()->None:
	"""
	カメラのプレビューを表示する

	・LCDサイズに縮小して表示
	・実際に撮影される写真と同じアスペクトレシオ
	・パターンマッチングで利用する領域を枠
	・フロントボタンを押すことで終了
	"""

	g.log( "WASHER","プレビュー")

	picam = Picamera2(0)
	picam.configure(
		picam.create_preview_configuration(
			main={"format": 'XRGB8888', "size": (PREVIEW_WIDTH, PREVIEW_HEIGHT)}))

	# 撮影開始
	picam.start()

	while True:
		img = picam.capture_array()
		img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

		## トリミング
		#w = img.shape[1]
		#h = img.shape[0]
		#img = img[
		#	int(h*WASHER_CAP_TRIM_TOP) :int(h*WASHER_CAP_TRIM_BOTTOM),
		#	int(w*WASHER_CAP_TRIM_LEFT):int(w*WASHER_CAP_TRIM_RIGHT)] #top:bottom, left:right
		
		img = Image.fromarray(img)
		draw = ImageDraw.Draw(img)
		draw.rectangle((
			int(PREVIEW_WIDTH *WASHER_CAP_TRIM_LEFT),
			int(PREVIEW_HEIGHT*WASHER_CAP_TRIM_TOP),
			int(PREVIEW_WIDTH *WASHER_CAP_TRIM_RIGHT),
			int(PREVIEW_HEIGHT*WASHER_CAP_TRIM_BOTTOM)),
			outline=(255,255,255))

		draw.text( (40, 160), "ボタンでプレビュー終了", font=info_title_font, fill="black" )

		g.image_main_buf.paste( img )
		g.epd_display()
		if g.front_button_status()==PUSH_1CLICK: break

	picam.stop()
	picam.close()

	g.log("WASER","プレビュー終了")

	