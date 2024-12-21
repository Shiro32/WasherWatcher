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
TEMP_LIGHT_CLOSE_OFF= "./pattern/icon_light_close_off.png"	# 予約なし
TEMP_LIGHT_CLOSE_2H	= "./pattern/icon_light_close_2h.png"	# ２ｈ予約
TEMP_LIGHT_CLOSE_4H	= "./pattern/icon_light_close_4h.png"	# ４ｈ予約

# 明るい・ドア開
TEMP_LIGHT_OPEN_OFF	= "./pattern/icon_light_open_off.png"	# 予約なし
TEMP_LIGHT_OPEN_2H	= "./pattern/icon_light_open_2h.png"	# ２ｈ予約
TEMP_LIGHT_OPEN_4H	= "./pattern/icon_light_open_4h.png"	# ４ｈ予約

# CASTELLIマークでOPEN/CLOSEを判定する
# 明るい部屋
TEMP_CASTELLI_LIGHT_OPEN  = "./pattern/castelli_light_open.png"
TEMP_CASTELLI_LIGHT_CLOSE = "./pattern/castelli_light_close.png"

# 暗い部屋
TEMP_CASTELLI_DARK_OPEN  = "./pattern/castelli_dark_open2.png"
TEMP_CASTELLI_DARK_CLOSE = "./pattern/castelli_dark_close2.png"


# テンプレートとマッチングの最低閾値
TEMP_MATCHING_THRESHOLD = 0.70	# OPEN/CLOSEどちらもこれを下回ると判定不能扱い
TEMP_TIMER_LED_THRESHOLD = 80	# LED点灯とみなす輝度

# 食洗器ドアが開放中と認識する秒数
# 一瞬中身を見た時なども、ドア開放（＝食器投入）とみなされないようにするため
DOOR_OPEN_CHECK_TIMER_s = 1*60

# 食洗器撮影写真サイズ
CAPTURE_WIDTH	= 1280 #2592
CAPTURE_HEIGHT	= 960 #1944

# プレビューサイズ
PREVIEW_ASPECT	= CAPTURE_WIDTH/CAPTURE_HEIGHT	# アスペクトレシオ（プレビュー用）
PREVIEW_WIDTH	= MAIN_WIDTH
PREVIEW_HEIGHT	= int(PREVIEW_WIDTH/PREVIEW_ASPECT)

# 撮影写真のトリミング領域（実際のパターンマッチングに使うのは狭い領域なので）
WASHER_CAP_TRIM_TOP		= 1/4*1
WASHER_CAP_TRIM_BOTTOM	= 1/4*4

WASHER_CAP_TRIM_LEFT	= 1/4*1
WASHER_CAP_TRIM_RIGHT	= 1/4*3

# --------------------- washer内のグローバル変数 ---------------------

# 食洗器の状態（状態を保持し続けるためにグローバル化）
# 暗くなる or 子機から問われた時はこれをもとに回答
washer_dishes	= WASHER_DISHES_EMPTY				# 汚れた食器が入っている（True）
washer_door		= WASHER_DOOR_CLOSE
washer_timer	= WASHER_TIMER_OFF

# カメラデバイスインスタンス
picam = 1

# 最後にドア閉塞を確認した時刻
# ここからの経過時間がDOOR_OPEN_CHECK_TIMER_sを超えると、開放とみなす
last_closed_door_time = datetime.datetime.now()

# ------------------------------------------------------------------------------
def init_camera():
	global picam

	picam = Picamera2()

	picam.configure(
		picam.create_preview_configuration(
			main={"format": 'XRGB8888', "size": (CAPTURE_WIDTH, CAPTURE_HEIGHT)}))
	picam.start()


def init_washer():
	global temp_dark_close, temp_dark_open
	global temp_light_close, temp_light_open

	temp_light_close = cv2.imread( TEMP_CASTELLI_LIGHT_CLOSE )
	temp_light_close = cv2.cvtColor( temp_light_close, cv2.COLOR_RGB2GRAY )

	temp_light_open  = cv2.imread( TEMP_CASTELLI_LIGHT_OPEN )
	temp_light_open  = cv2.cvtColor( temp_light_open, cv2.COLOR_RGB2GRAY )

	temp_dark_close  = cv2.imread( TEMP_CASTELLI_DARK_CLOSE )
	temp_dark_close  = cv2.cvtColor( temp_dark_close, cv2.COLOR_RGB2GRAY )

	temp_dark_open   = cv2.imread( TEMP_CASTELLI_DARK_OPEN )
	temp_dark_open   = cv2.cvtColor( temp_dark_open, cv2.COLOR_RGB2GRAY )

	init_camera()

# ------------------------------------------------------------------------------
def _capture_washer( full:bool )->np.ndarray:
	"""
	カメラモジュールで食洗器を撮影する
	（戻り値） トリミング加工された写真（np.ndarray）

	・フルサイズで撮影する
	・左右の真ん中、上下の下半分にトリミングする
	"""

	### TODO: もしかするとカメラ初期化は１回だけにした方がよいかも！！！
	global picam

	g.log( "WASHER","写真撮影")

	#picam = Picamera2()
	#picam.configure(
	#	picam.create_preview_configuration(
	#		main={"format": 'XRGB8888', "size": (CAPTURE_WIDTH, CAPTURE_HEIGHT)}))

	# 撮影
#	picam.start()
	img = picam.capture_array()
#	picam.stop()
#	picam.close()

	# カラーモードの調整なのかな
	chs = 1 if len(img.shape)==2 else img.shape[2]
	if chs==1:
		img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
	if chs==4:
		img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

	if not full:
		# トリミング
		w = img.shape[1]
		h = img.shape[0]
		img = img[
			int(h*WASHER_CAP_TRIM_TOP) :int(h*WASHER_CAP_TRIM_BOTTOM),
			int(w*WASHER_CAP_TRIM_LEFT):int(w*WASHER_CAP_TRIM_RIGHT)] #top:bottom, left:right

	g.log( "WASHER","写真撮影完了")
	#cv2.imwrite( "shot.png", img )
	return img

# ------------------------------------------------------------------------------
def _monitor_washer_now()->Tuple[int, int]:
	"""
	食洗器を撮影して、現在の状況を確認する
	あくまでも現状を見るだけで、過去の経緯（食器有無、洗浄済みなど）はかかわらない

	戻り値：(int x, int y)
	　x : ドアの状態（open/close）
	　y : タイマの状態（off/2h/4h）
	"""
	g.log( "WASHER","食洗器チェック開始")

	# 写真を撮影
	img   = _capture_washer(full=False)	# カラー
	img_g = cv2.cvtColor( img, cv2.COLOR_RGB2GRAY ) # グレー

	# OPEN/CLOSEの判定
	# 明るさに応じてOPEN/CLOSEの両方の相関係数を出す

	# どうせグレー化して比較するなら、DARKで良くない？
	if pi.read(CDS_PIN)==pigpio.HIGH:
		# 明るい場合
		g.log("WASHER", "CDS=明るい")
		result_cl = cv2.matchTemplate(img_g, temp_light_close, cv2.TM_CCOEFF_NORMED)
		result_op = cv2.matchTemplate(img_g, temp_light_open, cv2.TM_CCOEFF_NORMED)
	else:
		# 暗い場合
		result_cl = cv2.matchTemplate(img_g, temp_dark_close, cv2.TM_CCOEFF_NORMED)
		result_op = cv2.matchTemplate(img_g, temp_dark_open	, cv2.TM_CCOEFF_NORMED)
		g.log( "WASHER", "CDS=暗い")

	_, corr_cl, _, maxLoc_cl = cv2.minMaxLoc(result_cl)
	_, corr_op, _, maxLoc_op = cv2.minMaxLoc(result_op)
	g.log( "WASHER", f"CLOSE:{corr_cl:.2f} / OPEN:{corr_op:.2f}" )
	
	# 開閉どちらかのマークが読み取れなければ終了→この考え方はやめた
	#if corr_cl<TEMP_MATCHING_THRESHOLD or corr_op<TEMP_MATCHING_THRESHOLD:

	# 開閉どちらも閾値を下回る場合は、判定をあきらめる
	if max(corr_cl, corr_op) < TEMP_MATCHING_THRESHOLD:
		g.log( "WASHER", "判定不能（相関が低すぎる）")
		return WASHER_STATUS_UNKNOWN, WASHER_STATUS_UNKNOWN

	# 開閉の差が小さすぎる場合も、判定をあきらめる
	if abs(corr_cl - corr_op) < 0.1:
		g.log("WASHER", "判定不能（開閉に差がない）")
		return WASHER_STATUS_UNKNOWN, WASHER_STATUS_UNKNOWN

	# ドアの開閉に合わせて、検査すべきタイマーLEDの領域を設定
	if corr_cl>=corr_op:
		# CLOSE状態認識
		door = WASHER_DOOR_CLOSE
		# 2H
		timer2h_TL = maxLoc_cl[0]+temp_light_close.shape[1]	, maxLoc_cl[1]+20
		timer2h_BR = timer2h_TL[0]+12						, timer2h_TL[1]+12
		# 4H
		timer4h_TL = maxLoc_cl[0]+temp_light_close.shape[1]	, maxLoc_cl[1]+8
		timer4h_BR = timer4h_TL[0]+12						, timer4h_TL[1]+12

	else:
		# OPEN状態認識
		door = WASHER_DOOR_OPEN
		# 2H
		timer2h_TL = maxLoc_op[0]+temp_light_open.shape[1]	, maxLoc_op[1]+27
		timer2h_BR = timer2h_TL[0]+13						, timer2h_TL[1]+12
		# 4H
		timer4h_TL = maxLoc_op[0]+temp_light_open.shape[1]	, maxLoc_op[1]+10
		timer4h_BR = timer4h_TL[0]+13						, timer4h_TL[1]+13

	# 2Hと4HタイマーLEDの領域、赤の重さを算出
	box2 = img[ timer2h_TL[1]:timer2h_BR[1], timer2h_TL[0]:timer2h_BR[0] ]
	box4 = img[ timer4h_TL[1]:timer4h_BR[1], timer4h_TL[0]:timer4h_BR[0] ]
	c2 = box2.T[2].flatten().mean()
	c4 = box4.T[2].flatten().mean()

	g.log("WASHER", f"C2:{c2:.0f} / C4:{c4:.0f}")

	# いよいよLED判定
	# まれにc2,c4とも巨大になる時があり、片方だけ閾値を超えた際に発動
	if   c2>TEMP_TIMER_LED_THRESHOLD and c4<TEMP_TIMER_LED_THRESHOLD: timer = WASHER_TIMER_2H
	elif c4>TEMP_TIMER_LED_THRESHOLD and c2<TEMP_TIMER_LED_THRESHOLD: timer = WASHER_TIMER_4H
	else							 : timer = WASHER_TIMER_OFF

	g.log("WASHER", f"一致検出（DOOR={_door(door)}/TIMER={_timer(timer)}）")
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
	return _door(washer_door)+","+_timer(washer_timer)+","+_dishes(washer_dishes)

# ------------------------------------------------------------------------------
def monitor_washer()->None:
	"""
	食洗器を撮影して、現在の状況を確認する
	数十秒ごとにタイマーでメインルーチンからコールされる

	・下請け（_monitor_washer_now）で現在の状態（ドア・タイマ）を調べる
	・状態がunknownなら終了
	・ドア開→汚れ食器あり
	・ドア閉→なにもしない
	・タイマーオフ→過去にタイマーセットされているなら、洗浄完了扱い
	・タイマーオン→汚れ食器なし
	"""
	global washer_dishes, washer_door, washer_timer
	global last_closed_door_time

	start = datetime.datetime.now()

	# 直前値を保持
	old_washer_dishes	= washer_dishes
	old_washer_door		= washer_door
	old_washer_timer	= washer_timer

	# １ショット撮影してドア・タイマの状態を獲得
	door, timer = _monitor_washer_now()

	# 状態不明なら諦める（ガード節）
	if door==WASHER_STATUS_UNKNOWN: return


	# 最新の状態をstatic変数に反映する
	washer_door = door
	washer_timer = timer

	# ドア・タイマによるdishesの状態設定・アクション

	# ドアが閉まっている
	if door==WASHER_DOOR_CLOSE:
		# 最後にドアが閉まっていた時刻を記憶
		last_closed_door_time = datetime.datetime.now()

		# ドア閉で警報は１回だけ
		if old_washer_door == WASHER_DOOR_OPEN:
			g.log("WASHER", "ドアがしまりました")
			g.talk("do'aga simattayo")

	# ドアが開いている
	else:
		# 食器は入っていない
		if washer_dishes==WASHER_DISHES_EMPTY:
			# 一定時間空けたなら、汚れた食器を入れたハズ
			if (datetime.datetime.now()-last_closed_door_time).seconds > DOOR_OPEN_CHECK_TIMER_s:
				# 食器ステータスを「汚れ」に
				washer_dishes = WASHER_DISHES_DIRTY
				g.log("WASHER", "ドアが長時間開きました（EMPTY→DIRTY）")
				g.talk("shokki'wo iretemasune.")
				g.talk("ta'ima-no/se'ttowo wasu'renaide/kuda'saine-")

				# 30分後には念のため確認開始（夜照明を消す前の事前チェックサービス）
				schedule.every(30).minutes.do(check_washer).tag("check_washer")

		# すでに食器が入っている
		elif washer_dishes==WASHER_DISHES_DIRTY:
			g.log("WASHER", "ドア開放を検出（DIRTY）")
			# 音声は開けた時の１回だけ
			if old_washer_door == WASHER_DOOR_CLOSE:
				g.talk("ta'ima-no se'ttowo wasurezuni.")

		# 洗浄済みの食器が入っている
		# 開けたということは、食器を取り出そうとしているタイミングのハズ
		else:
			g.log("WASHER", "ドア開放を検出（WASHED）")
			washer_dishes = WASHER_DISHES_EMPTY	# 食器「空」にする
			# 音声は開けた時の１回だけ
			if old_washer_door == WASHER_DOOR_CLOSE:
				g.talk("shokki'wa senjo'uzumi/de'suyo.")
				start_alert_washed()


	#if old_washer_door != door:
	#	# 1.ドアが開いている（食器を入れている or 出している）
	#	if door==WASHER_DOOR_OPEN:
	#		# 洗浄済みの食器を出すとき
	#		if washer_dishes==WASHER_DISHES_WASHED:
	#			g.log("WASHER", "食器は洗浄済みですよ")
	#			g.talk("sho'kkiwa senjo'uzumi/de'suyo.")
	#			start_alert_washed()
	#			washer_dishes = WASHER_DISHES_EMPTY	# 食器「空」にする

	#		else:
	#			g.log("WASHER", "ドアが開きました")
	#			g.talk("doa'ga hirakimasita")

	#			# 食器ステータスを「汚れ」に
	#			washer_dishes = WASHER_DISHES_DIRTY
	#			# 30分後には念のため確認開始（夜照明を消す前の事前チェックサービス）
	#			schedule.every(30).minutes.do(check_washer).tag("check_washer")

	#	# 2.ドアが閉まっている（食器には直接の変化なし）
	#	if door==WASHER_DOOR_CLOSE:
	#		g.log("WASHER", "ドアがしまりました")
	#		g.talk("do'aga simattayo")

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

	g.log("WASHER", f"現状認識：{washer_status()} 【{(datetime.datetime.now()-start).seconds}秒】")
	return

# ------------------------------------------------------------------------------
def check_washer( call_from_child:bool=False )->bool:
	"""
	食洗器の警報判断を行う（CDS明→暗、子機呼び出しタイミング）
	子機から呼び出されたり、照明が消えた時（CDS）に呼び出される
	
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
			.do(stop_alert_timer_ok).tag("stop_alert_timer_ok")

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
#	g.talk("sho'kkiwa ara'tte/ari'masuyo-")

def stop_alert_washed()->None:
	"""
	ボタンでダイアログ消したときの扱い
	"""
	g.log("TIMER","終了～")
	g.talk("pipi")
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

	global picam

	g.clear_image()
	g.epd_display

	g.log("WASHER","プレビュー")
	g.talk("ka'merano mu'kiwo/chouseisimasu.")
	g.talk("bota'nde/shu'uryou/de'su")

	# いったん、カメラを停める
	picam.stop()
	picam.close()

	# プレビュー用に再起動
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
		
		#img = cv2.resize(img, None, fx=4, fy=4,interpolation=cv2.INTER_CUBIC)
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

	# カメラを停める
	picam.stop()
	picam.close()

	# カメラを再起動
	init_camera()

	g.talk("ka'mera/cho'usei shuu'ryou")
	g.log("WASER","プレビュー終了")

	