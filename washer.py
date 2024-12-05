#!usr/bin/env python
# -*- coding: utf-8 -*-

# 食洗器監視のモジュール
# ラズパイカメラで読み取った写真を、OpenCVのパターンマッチングで判定
#
# ステータスは３つあり、２つの情報から推定する（ドア開閉・タイマー）
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
import schedule

from cfg import *   # 定数関係
import globals as g # グローバル変数・関数

# --------------------- washer内の定数 ---------------------
# テンプレート写真

# 明るい・ドア閉
TEMP_LIGHT_CLOSE_OFF= "./pattern/light_close_off.png"	# 予約なし
TEMP_LIGHT_CLOSE_2H	= "./pattern/light_close_2h.png"	# ２ｈ予約
TEMP_LIGHT_CLOSE_4H	= "./pattern/light_close_4h.png"	# ４ｈ予約

# 明るい・ドア開
TEMP_LIGHT_OPEN_OFF	= "./pattern/light_open_off.png"	# 予約なし
TEMP_LIGHT_OPEN_2H	= "./pattern/light_open_2h.png"		# ２ｈ予約
TEMP_LIGHT_OPEN_4H	= "./pattern/light_open_4h.png"		# ４ｈ予約

# テンプレートとマッチングの最低閾値
TEMP_MATCHING_THRESHOULD = 0.85

# 食洗器撮影写真サイズ
CAPTURE_WIDTH	= 2592
CAPTURE_HEIGHT	= 1944

# プレビューサイズ
PREVIEW_ASPECT	= CAPTURE_WIDTH/CAPTURE_HEIGHT	# アスペクトレシオ（プレビュー用）
PREVIEW_WIDTH	= MAIN_WIDTH
PREVIEW_HEIGHT	= int(PREVIEW_WIDTH/PREVIEW_ASPECT)

# 撮影写真のトリミング領域（実際のパターンマッチングに使うのは狭い領域なので）
WASHER_CAP_TRIM_TOP		= 1/4*1
WASHER_CAP_TRIM_BOTTOM	= 1/4*3

WASHER_CAP_TRIM_LEFT	= 1/4*1
WASHER_CAP_TRIM_RIGHT	= 1/4*3

# --------------------- washer内のグローバル変数 ---------------------

# 食洗器の状態（状態を保持し続けるためにグローバル化）
# 暗くなる or 子機から問われた時はこれをもとに回答
washer_dishes	= WASHER_DISHES_EMPTY				# 汚れた食器が入っている（True）
washer_door		= WASHER_DOOR_CLOSE
washer_timer	= WASHER_TIMER_OFF


#def door_label()->str:
#	return "OP" if washer_door==WASHER_DOOR_OPEN else "CL"

#def dishes_label()->str:
#	return "IN" if dirty_dishes else "NO"

#def timer_label()->str:

# ------------------------------------------------------------------------------
def _capture_washer()->np.ndarray:
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

	g.log( "WASHER","写真撮影完了")
	cv2.imwrite( "shot.png", img )
	return img

# ------------------------------------------------------------------------------
def _pattern_matching(image, open_template, close_template)->Tuple[float, int]:
	"""
	現在の食洗器の写真と、テンプレートを照合して一致度を計算する

	・現在の食洗器の中に、与えられたテンプレートが含まれている相関係数を計算

	引数：
		image			: 現在の食洗器の写真（カメラ撮影したもの）
		open_template	: 開いている食洗器のテンプレ
		close_template	: 閉まっている食洗器のテンプレ

	戻り値：（x,y）
		x : 相関係数
		y : ドア開閉状態
	"""
	g.log("WASHER","パターンマッチング")

	img    = cv2.cvtColor( image, cv2.COLOR_RGB2GRAY )
	op_tmp = cv2.cvtColor( cv2.imread(open_template) , cv2.COLOR_RGB2GRAY )
	cl_tmp = cv2.cvtColor( cv2.imread(close_template), cv2.COLOR_RGB2GRAY )

	corr = 0

	# open側のパターンマッチング
	op_result = cv2.matchTemplate(img, op_tmp, cv2.TM_CCOEFF_NORMED)
	_, op_corr, _, _ = cv2.minMaxLoc(op_result)

	# close側のパターンマッチング
	cl_result = cv2.matchTemplate(img, cl_tmp, cv2.TM_CCOEFF_NORMED)
	_, cl_corr, _, _ = cv2.minMaxLoc(cl_result)

	if op_corr > cl_corr:
		return op_corr, WASHER_DOOR_OPEN
	else:
		return cl_corr, WASHER_DOOR_CLOSE


# ------------------------------------------------------------------------------

def _pattern_matching_zoom(image, template, max_zoom)->Tuple[float, float]:
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
	g.log("WASHER","パターンマッチング")

	img = cv2.cvtColor( image, cv2.COLOR_RGB2GRAY )
	tpl = cv2.cvtColor( cv2.imread(template), cv2.COLOR_RGB2GRAY )

	# 拡大を許さないパターン（TODO:もうやらないので、消していいカモ）
	if max_zoom==100:
		result = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
		_, corr, _, _ = cv2.minMaxLoc(result)

		return corr, 100

	# 拡大を許すパターン（ドアを開けている状態を想定）
	else:
		corr = 0
		zoom = 100

		for i in range(100, max_zoom+1 , 5):

			# テンプレートの拡大
			tpl2 = cv2.resize(tpl, None, fx=i/100, fy=i/100,interpolation=cv2.INTER_CUBIC)

			result = cv2.matchTemplate(img, tpl2, cv2.TM_CCOEFF_NORMED)
			_, v, _, _ = cv2.minMaxLoc(result)

			if v>corr:
				corr = v
				zoom = i

		return corr, zoom

# ------------------------------------------------------------------------------
def _monitor_washer_now()->None:
	"""
	食洗器を撮影して、現在の状況を確認する
	あくまでも現状を見るだけで、過去の経緯（食器有無、洗浄済みなど）はかかわらない

	戻り値：(int x, int y)
	　x : ドアの状態（open/close）
	　y : タイマの状態（off/2h/4h）
	"""
	# TODO:ズームで全部調べるのではなく、開閉１枚ずつのチェックにすべき

	g.log( "WASHER","食洗器チェック開始")

	# 写真を撮影
	img = _capture_washer()

	# 3パターン（オフ、2H、4H）でパターンマッチングして、一番スコアの高いものを採用
	results = [] # {ドア状態、タイマー状態、相関値}


	# タイマー０
	c1 = _pattern_matching(img, TEMP_LIGHT_CLOSE_OFF)
	c2 = _pattern_matching(img, TEMP_LIGHT_OPEN_OFF )
	results.append( {"DOOR":WASHER_DOOR_CLOSE, "TIMER":WASHER_TIMER_OFF, "CORR":c1} )
	results.append( {"DOOR":WASHER_DOOR_OPEN,  "TIMER":WASHER_TIMER_OFF, "CORR":c2} )
	

	# タイマー2H
	c1 = _pattern_matching(img, TEMP_LIGHT_CLOSE_2H)
	c2 = _pattern_matching(img, TEMP_LIGHT_OPEN_2H )
	results.append( {"DOOR":WASHER_DOOR_CLOSE, "TIMER":WASHER_TIMER_2H, "CORR":c1} )
	results.append( {"DOOR":WASHER_DOOR_OPEN,  "TIMER":WASHER_TIMER_2H, "CORR":c2} )

	# タイマー4H
	c1 = _pattern_matching(img, TEMP_LIGHT_CLOSE_4H)
	c2 = _pattern_matching(img, TEMP_LIGHT_OPEN_4H )
	results.append( {"DOOR":WASHER_DOOR_CLOSE, "TIMER":WASHER_TIMER_4H, "CORR":c1} )
	results.append( {"DOOR":WASHER_DOOR_OPEN,  "TIMER":WASHER_TIMER_4H, "CORR":c2} )

	#昇順ソート
	results = sorted(results, key=lambda x:x["CORR"], reverse=True)

	#ランキングをLOG出力
	for x in results:
		door  = x["DOOR"]
		timer = x["TIMER"]
		corr  = x["CORR"]

		g.log( "WASHER", f"DOOR:{_door(door)} / TIMER:{_timer(timer)} / CORR:{corr:.3f}" )

	# 一致度が最低ラインを下回っていたら、素直に「分からない」と回答
	if results[0]["CORR"] < TEMP_MATCHING_THRESHOULD:
		g.log("WASHER","判定できず")
		return WASHER_STATUS_UNKNOWN, WASHER_STATUS_UNKNOWN

	# 一致が見つかっているならそれを返す
	else:
		door  = results[0]["DOOR"]
		timer = results[0]["TIMER"]

		g.log("WASHER", f"一致検出（DOOR:{_door(door)}/TIMER{_timer(timer)}）")
		return door, timer

# ------------------------------------------------------------------------------
def _door(door:int)->str:
	if   door==WASHER_DOOR_CLOSE: return "CLOSE"
	elif door==WASHER_DOOR_OPEN : return "OPEN"
	else: return "--"

def _timer(timer:int)->str:
	if   timer==WASHER_TIMER_OFF: return "OFF"
	elif timer==WASHER_TIMER_2H : return "2H"
	elif timer==WASHER_TIMER_4H : return "4H"
	else: return "--"

def _dishes(dishes:int)->str:
	if   dishes==WASHER_DISHES_EMPTY : return "EMPTY"
	elif dishes==WASHER_DISHES_DIRTY : return "DIRTY"
	elif dishes==WASHER_DISHES_WASHED: return "WASHED"
	else: return "--"

def washer_status()->str:
	return _door(washer_door)+"/"+_timer(washer_timer)+"/"+_dishes(washer_dishes)

# ------------------------------------------------------------------------------
debug_door = False
debug_timer = False

def monitor_washer()->None:
	"""
	食洗器を撮影して、現在の状況を確認する

	・下請け（_monitor_washer_now）で現在の状態（ドア・タイマ）を調べる
	・状態がunknownなら終了
	・ドア開→汚れ食器あり
	・ドア閉→なにもしない
	・タイマーオフ→過去にタイマーセットされているなら、洗浄完了扱い
	・タイマーオン→汚れ食器なし
	"""
	global washer_dishes, washer_door, washer_timer

	# 直前値を保持
	old_washer_dishes	= washer_dishes
	old_washer_door		= washer_door
	old_washer_timer	= washer_timer

	# デバッグ変数が定義されていたら
	if debug_door or debug_timer:
		g.log( "WASHER", "DEBUGで食洗器チェック")
		door = WASHER_DOOR_CLOSE
		timer = WASHER_TIMER_OFF
		if debug_door=="open"	: door = WASHER_DOOR_OPEN	;debug_door=""
		if debug_door=="close"	: door = WASHER_DOOR_CLOSE	;debug_door="" 
		if debug_timer=="off"	: timer = WASHER_TIMER_OFF	;debug_timer=""
		if debug_timer=="2H"	: timer=WASHER_TIMER_2H		;debug_timer=""
	else:
		# １ショット撮影してドア・タイマの状態をチェック
		door, timer = _monitor_washer_now()

		# 状態不明なら諦める（ガード節）
		if door==WASHER_STATUS_UNKNOWN: return


	# 最新の状態をstatic変数に反映する
	washer_door = door
	washer_timer = timer

	# ドア・タイマによるdishesの状態設定・アクション

	# ドア状態の変化検出
	if old_washer_door != door:
		# 1.ドアが開いている（食器を入れている or 出している）
		if door==WASHER_DOOR_OPEN:
			# 洗浄済みの食器を出すとき
			if washer_dishes==WASHER_DISHES_WASHED:
				g.log("WASHER", "食器は洗浄済みですよ")
				g.talk("sho'kkiwa senjo'uzumi/de'suyo.")
				start_alert_washed()
				washer_dishes = WASHER_DISHES_EMPTY	# 食器「空」にする

			else:
				g.log("WASHER", "ドアが開きました")
				g.talk("doa'ga hirakimasita")

				# 食器ステータスを「汚れ」に
				washer_dishes = WASHER_DISHES_DIRTY
				# 30分後には念のため確認開始（夜照明を消す前の事前チェックサービス）
				schedule.every(30).minutes.do(check_washer).tag("check_washer")

		# 2.ドアが閉まっている（食器には直接の変化なし）
		if door==WASHER_DOOR_CLOSE:
			g.log("WASHER", "ドアがしまりました")
			g.talk("do'aga simattayo")

	# タイマ状態の変化検出
	if old_washer_timer!=timer:
		# 3.タイマーがオフ（直前までタイマONなら洗浄開始のハズ！！）
		if timer==WASHER_TIMER_OFF:
			g.log("WASHER", "洗浄が始まりました")
			washer_dishes=WASHER_DISHES_WASHED

		# 4.タイマーが2hまたは4h（食器には直接の変化なし）
		if timer==WASHER_TIMER_2H or timer==WASHER_TIMER_4H:
			g.log("WASHER","タイマーがセットされました")
			g.talk("ta'ima-ga settosaremasita.")

	g.log("WASHER", f"現状認識：{washer_status()}")
	return

# ------------------------------------------------------------------------------
def check_washer( call_from_child:bool=False )->bool:
	"""
	食洗器の警報判断を行う（CDS明→暗、子機呼び出しタイミング）

	引数：
	　call_from_child(bool)
	　　： 子機から呼ばれてチェックする場合はTrue
	　　　　その場合は、無駄に音声発生しない（だけかな？）

	戻り値：
	・True  : 正常（食器なし・タイマセット済み）
	・False : 異常（食器あり・タイマセットなし） 
	"""
	global washer_dishes, washer_door, washer_timer
	global _call_from_child

	g.log("WASHER", f"現状認識：{washer_status()}")
	schedule.clear("check_washer") # 夜の照明を消す前の30分チェックのキャンセル

	# なし→OK
	if washer_dishes==WASHER_DISHES_EMPTY:
		if call_from_child==False:
			g.log("WASHER","食器は入っていません")
			g.talk( "shokki'wa ha'itte/imase'n.")
		return True
	
	# 洗浄済み→OK
	if washer_dishes==WASHER_DISHES_WASHED:
		if call_from_child==False:
			g.log("WASHER", "洗浄済みです")
			g.talk( "shokki'wa se'njouzumi de'su.")
		return True

	# 食器が入っているときは、タイマの設定によりOK/NG
	elif washer_dishes==WASHER_DISHES_DIRTY:

		# タイマがセットされていない→NG
		if washer_timer==WASHER_TIMER_OFF:
			if call_from_child==False:
				g.log("WASHER","食器があるのにタイマーセットされていません！")
				g.talk( "ta'ima-ga se'ttosareteimasen.")

			if not call_from_child: start_alert_dirty_dishes() # 最重要機能！
			return False

		# タイマがセットされている→OK
		else:
			if call_from_child==False:
				g.log("WASHER","食器が入っていて、タイマーはセットされています！")
				g.talk( "shokuse'nkiwa daijo'ubu desu.")
				g.talk( "a'nsinsite oya'suminasai.")

			if not call_from_child: start_alert_timer_ok()	# いらない気もするが・・・ TODO:
			return True

# ------------------------------------------------------------------------------
def start_alert_dirty_dishes()->None:
	"""
	汚れた食器＆タイマー未セットの警告ダイアログ
	"""
	g.log("DIRTY","汚れ警報開始")
	alert_dirty_dishes()
	schedule.every(WASHER_DIRTY_DISHES_INTERVAL_s).seconds\
			.do(alert_dirty_dishes).tag("alert_dirty_dishes")

	schedule.every(WASHER_DIRTY_DISHES_TIMER_s).seconds\
			.do(stop_alert_dirty_dishes).tag("stop_alert_dirty_dishes")

def alert_dirty_dishes()->None:
	"""
	タイマー未セット警告のハンドラー
	"""
	g.set_dialog( PIC_DIRTY, stop_alert_dirty_dishes )
	g.log("ALERT", "タイマーセットされておらんよ")
	g.talk("abunaizo-")

def stop_alert_dirty_dishes()->None:
	"""
	ボタンでダイアログ消したときの扱い
	"""
	g.log("DIRTY","警報終了～")
	g.talk("ke'ihou tei'si")
	schedule.clear("alert_dirty_dishes")
	schedule.clear("stop_alert_dirty_dishes")
	g.update_display_immediately()

# ------------------------------------------------------------------------------
def start_alert_timer_ok()->None:
	"""
	タイマーがセットされていて問題ない場合のアラート（いる？）
	"""
	g.log("TIMER","OK警報開始")
	alert_timer_ok()
	schedule.every(WASHER_DIRTY_DISHES_INTERVAL_s).seconds\
			.do(alert_timer_ok).tag("alert_timer_ok")

	schedule.every(WASHER_DIRTY_DISHES_TIMER_s).seconds\
			.do(stop_alert_timer_ok).tag("stop_alert_timer_Ok")

def alert_timer_ok()->None:
	"""
	タイマーセット済みハンドラ～
	"""
	g.set_dialog( PIC_DIRTY_OK, stop_alert_timer_ok )
	g.log("TIMER", "タイマーセットされてますよ～")

def stop_alert_timer_ok()->None:
	"""
	ボタンでダイアログ消したときの扱い
	"""
	g.log("TIMER","警報終了～")
	g.talk("ke'ihou tei'si")
	schedule.clear("alert_timer_ok")
	schedule.clear("stop_alert_timer_ok")
	g.update_display_immediately()

# ------------------------------------------------------------------------------
def start_alert_washed()->None:
	"""
	ちゃんと洗浄された報告（朝に出番のはず）
	"""
	g.log("TIMER","警報開始")
	alert_washed()
	schedule.every(WASHER_DIRTY_DISHES_INTERVAL_s).seconds\
			.do(alert_washed).tag("alert_washed")

	schedule.every(WASHER_DIRTY_DISHES_TIMER_s).seconds\
			.do(stop_alert_washed).tag("stop_alert_washed")

def alert_washed()->None:
	"""
	洗浄済み警報ハンドラ～
	"""
	g.set_dialog( PIC_DIRTY_OK, stop_alert_washed )
	g.log("TIMER", "食器は洗浄済み！")
	g.talk("sho'kkiwa ara'tte/ari'masuyo-")

def stop_alert_washed()->None:
	"""
	ボタンでダイアログ消したときの扱い
	"""
	g.log("TIMER","終了～")
	g.talk("ke'ihou tei'si")
	schedule.clear("alert_washed")
	schedule.clear("stop_alert_washed")
	g.update_display_immediately()

# ------------------------------------------------------------------------------
def preview_washser()->None:
	"""
	カメラのプレビューを表示する

	・LCDサイズに縮小して表示
	・実際に撮影される写真と同じアスペクトレシオ
	・パターンマッチングで利用する領域を枠
	・フロントボタンを押すことで終了
	"""
	g.clear_image()
	g.epd_display

	g.log("WASHER","プレビュー")
	g.talk("ka'merano mu'kiwo/chouseisimasu.")
	g.talk("bota'nde/shu'uryou/de'su")

	picam = Picamera2()
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
		g.image_main_buf.paste( img )

		draw = ImageDraw.Draw(g.image_main_buf)
		draw.rectangle((
			int(PREVIEW_WIDTH *WASHER_CAP_TRIM_LEFT),
			int(PREVIEW_HEIGHT*WASHER_CAP_TRIM_TOP),
			int(PREVIEW_WIDTH *WASHER_CAP_TRIM_RIGHT),
			int(PREVIEW_HEIGHT*WASHER_CAP_TRIM_BOTTOM)),
			outline=(255,255,255))

		draw.text( (40, 210), "左側のボタンで終了", font=normalFont, fill="black" )

		g.epd_display()
		if g.front_button_status()==PUSH_1CLICK: break

	picam.stop()
	picam.close()

	g.talk("ka'mera/cho'usei shuu'ryou")
	g.log("WASER","プレビュー終了")

	