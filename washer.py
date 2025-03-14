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
# 最初に正確に２情報（ドア開閉・タイマー）を得ることが大切だけど、
# しょぼいカメラで画像認識しているので、非常に難航・・・。
#
#　V1 LED自体を検出１
#	・LED自体をパターンマッチングで見つけようとした
#	・テンプレートは隣のボタン（予約）を込みで撮影
#	・ドア開閉はテンプレートのズーム率で判定
#	・４Hの暗さで見つけられずエラー多発＆遅い
#	・１判定＝1分程度（論外）
#
# V2 LED自体を検出２
#	・ズーム率を変えて探すのは時間がかかりすぎる反省
#	・OPENとCLOSEの２パターンをマッチングさせ、近い方を採用する
#	・タイマ（３パターン）×開閉（２パターン）＝６回マッチング
#	・１判定＝40秒程度
#
# V3 カステリを検出
#	・食洗器に貼ったカステリシールを目印に探す
#	・カステリマークの横にあるLEDの輝度（というか赤ドット）を数える
#	・カステリ（開閉）の２回しかマッチングしない
#	・１秒以内
#
# V4 ３ボタンを検出
#	・カメラ性能が悪すぎて、カステリマークが判別できない（ほぼ単なる丸）
#	・３ボタン並び（電源・モード・予約）を検出して位置を確定し、LEDを数える
#	・１秒以内
#
#	TODO: LEDの赤要素を数えようとしているが、赤外線カメラではもともと無理な気がする
#			輝度を使ってみてはどうか（明るいドット数を数える）


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

# LED→カステリシール→３ボタン並び、と進化してきた
TEMP_LIGHT_OPEN  = "./pattern/3buttons_light_open.png"
TEMP_LIGHT_CLOSE = "./pattern/3buttons_light_close.png"
TEMP_DARK_OPEN   = "./pattern/3buttons_dark_open.png"
TEMP_DARK_CLOSE  = "./pattern/3buttons_dark_close.png"


# テンプレートとマッチングの最低閾値
TEMP_DAY_MATCHING_THRESHOLD 	= 0.65	# OPEN/CLOSEどちらもこれを下回ると判定不能扱い
TEMP_NIGHT_MATCHING_THRESHOLD	= 0.75	# OPEN/CLOSEどちらもこれを下回ると判定不能扱い

MATCHING_FREQ  			= 2		# ノイズ対策で多頻度監視する回数
MATCHING_TIMER4_FREQ	= 20	# 特にLED4がすぐに消えちゃうので、超念入りに頻度監視する

TEMP_TIMER_LED_RATIO_THREDHOLF	= 1.20
TEMP_TIMER_LED_THRESHOLD = 55	# LED点灯とみなす輝度(暗い＝５０、明るい＝６０)

# 食洗器ドアが開放中と認識する秒数
# 一瞬中身を見た時なども、ドア開放（＝食器投入）とみなされないようにするため
# でも、本当に食器を入れる時も邪魔なので、あまり長く開けていないかもしれない
DOOR_OPEN_CHECK_TIMER_s = 1*60

# 食洗器撮影写真サイズ
CAPTURE_WIDTH	= 1280 #2592
CAPTURE_HEIGHT	= 960 #1944

# プレビューサイズ
PREVIEW_ASPECT	= CAPTURE_WIDTH/CAPTURE_HEIGHT	# アスペクトレシオ（プレビュー用）
PREVIEW_WIDTH	= MAIN_WIDTH
PREVIEW_HEIGHT	= int(PREVIEW_WIDTH/PREVIEW_ASPECT)

# 撮影写真のトリミング領域（実際のパターンマッチングに使うのは狭い領域なので）
WASHER_CAP_TRIM_TOP		= 1/6*3
WASHER_CAP_TRIM_BOTTOM	= 1/6*5

WASHER_CAP_TRIM_LEFT	= 1/6*2
WASHER_CAP_TRIM_RIGHT	= 1/6*4

# --------------------- washer内のグローバル変数 ---------------------

# 食洗器の状態（状態を保持し続けるためにグローバル化）
# 暗くなる or 子機から問われた時はこれをもとに回答
washer_dishes	= WASHER_DISHES_EMPTY				# 汚れた食器が入っている（True）
washer_door		= WASHER_STATUS_UNKNOWN
washer_timer	= WASHER_STATUS_UNKNOWN

# カメラデバイスインスタンス
picam = 1

# 最後にドア閉塞を確認した時刻
# ここからの経過時間がDOOR_OPEN_CHECK_TIMER_sを超えると、開放とみなす
last_closed_door_time = datetime.datetime.now()

# 過剰な「OK」音声を抑制するためのフラグ
# CDSのオン・オフの都度、「タイマー良好」を発声するのを抑制
# セット：タイマー初検出時（OFF→ON）
# クリア：状態確認し、音声発信したとき（通知したので以後しゃべらない）
need_to_notice_timer_set = False


# カメラの見通しが悪い時の警報用フラグ
# 見えていない間に多重コールしないようにしているだけ
camera_unseen = False

# デバッグ用
newest_matching_image = ""
save_matching_flag = False
save_matching_flag2 = False

# ------------------------------------------------------------------------------
def init_washer():
	"""
	アプリ起動時に、wwのinit_bootから１回だけ呼ばれる初期化処理
	テンプレートの準備、カメラデバイスの初期化など
	"""
	global temp_dark_close, temp_dark_open
	global temp_light_close, temp_light_open

	temp_light_close = _read_template(TEMP_LIGHT_CLOSE)
	temp_light_open  = _read_template(TEMP_LIGHT_OPEN)
	temp_dark_close  = _read_template(TEMP_DARK_CLOSE)
	temp_dark_open   = _read_template(TEMP_DARK_OPEN )

	init_camera()

def init_camera():
	global picam

	picam = Picamera2()

	picam.configure(
		picam.create_preview_configuration(
			main={"format": 'XRGB8888', "size": (CAPTURE_WIDTH, CAPTURE_HEIGHT)}))
	picam.start()

def _read_template(fname:str):
	a = cv2.imread(fname)
	return cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)

# ------------------------------------------------------------------------------
def _capture_washer( full_size:bool=False )->np.ndarray:
	"""
	カメラモジュールで食洗器を撮影する
	（戻り値） トリミング加工された写真（np.ndarray、BGRカラー）

	・フルサイズで撮影する
	・左右の真ん中、上下の下半分にトリミングする
	"""

	global picam, save_matching_flag2

	# 撮影
	img = picam.capture_array()
	img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

	if not full_size:
		# トリミング
		w = img.shape[1]
		h = img.shape[0]
		img = img[
			int(h*WASHER_CAP_TRIM_TOP) :int(h*WASHER_CAP_TRIM_BOTTOM),
			int(w*WASHER_CAP_TRIM_LEFT):int(w*WASHER_CAP_TRIM_RIGHT)] #top:bottom, left:right

	if save_matching_flag2:
		save_matching_flag = False
		cv2.imwrite("raw.png", img)

	return img

# ------------------------------------------------------------------------------
def _matching_washer()->Tuple[int, int]:
	"""
	複数回のパターンマッチングの履歴により、現在のDOORとTIMERを判定する
	下請けとして_matching_one_washerを呼び出す
	本来は、_matching_one_washerの結果をそのまま使えばよい（従来はそうしていた）が、
	ちょいちょいとエラーが起きるので、複数回続いた場合のみ、状態変化するようにする
	特に、Timer4（LED 4H）がちょっとした具合でOFFになるため、念入りに
	
	メインルーチン（schedule)
	monitor_washer			→ 過去の状態も踏まえ、DOOR/TIMER/DISHESを決める
	_matching_washer★		→ one_washerの認識エラー対策で、頻度監視する
	_matching_one_washer	→ パターンマッチングでDOOR/TIMERを判定する
	_capture_washer			→ キャプチャーする
	
	戻り値：(int x, int y)
	　x : ドアの状態（open/close/unknown）
	　y : タイマの状態（off/2h/4h/unknown）
	"""
	g.log( "MATCHING","食洗器チェック開始")

	# 下請けのマッチング処理を読んで、現在の値を獲得する
	door, timer = _matching_one_washer()

	# １．ドア判定の頻度監視
	# 前回と同じ「状態」なら頻度を増やす
	if door == _matching_washer.prev_door and door != WASHER_STATUS_UNKNOWN:
		_matching_washer.door_counter += 1
		
		# 頻度が達したなら状態変化
		if _matching_washer.door_counter >= MATCHING_FREQ:
			_matching_washer.current_door = door

	# 前回と異なる「状態」またはUnknownなら頻度を０に戻す
	else:
		_matching_washer.door_counter = 0
		_matching_washer.prev_door = door

	# ２．タイマーの頻度監視
	# 4時間タイマー（TIEMR_4H）は暗くてOFFになりがちなので、頻度監視を強める
	if _matching_washer.current_timer == WASHER_TIMER_4H:
		freq_thr = MATCHING_TIMER4_FREQ
	else:
		freq_thr = MATCHING_FREQ

	if timer == _matching_washer.prev_timer and timer != WASHER_STATUS_UNKNOWN:
		_matching_washer.timer_counter += 1
		if _matching_washer.timer_counter >= freq_thr: _matching_washer.current_timer = timer
	else:
		_matching_washer.timer_counter = 0
		_matching_washer.prev_timer = timer

	g.log("MATCHING",
	   f"DOOR:{_door(_matching_washer.current_door)}({_matching_washer.door_counter}) / TIMER:{_timer(_matching_washer.current_timer)}({_matching_washer.timer_counter})")

	return _matching_washer.current_door, _matching_washer.current_timer

# _matching_washerのstatic変数たち
# TODO: グローバル変数を増やしたくなくて、_matching_washerの内部オブジェクトとして変数を作っているが、意味があるのか・・・？
_matching_washer.current_door	= WASHER_STATUS_UNKNOWN
_matching_washer.current_timer	= WASHER_STATUS_UNKNOWN
_matching_washer.prev_door 		= WASHER_STATUS_UNKNOWN
_matching_washer.prev_timer 	= WASHER_STATUS_UNKNOWN
_matching_washer.door_counter	= 0
_matching_washer.timer_counter	= 0


# TODO: CDSの状態をキープする
cds_status = True

# ------------------------------------------------------------------------------
def _matching_one_washer()->Tuple[int, int]:
	"""
	食洗器を撮影して、パターンマッチング（OpenCV）により、現在のDOORとTIMERを判定する
	あくまでも現状を見るだけで、過去の経緯（食器有無、洗浄済みなど）はかかわらない
	_captureを除けば、最下層の処理ルーチン

	TODO: CDSの変化（明→暗、暗→明）でカメラが安定せずに誤判する可能性がある？
	TODO: CDSが変化したら、多頻度監視をリセットする？？

	メインルーチン（schedule)
	monitor_washer			→ 過去の状態も踏まえ、DOOR/TIMER/DISHESを決める
	_matching_washer		→ one_washerの認識エラー対策で、頻度監視する
	_matching_one_washer★	→ パターンマッチングでDOOR/TIMERを判定する
	_capture_washer			→ キャプチャーする

	戻り値：(int x, int y)
	　x : ドアの状態（open/close/unknown）
	　y : タイマの状態（off/2h/4h/unknown）
	"""
	global newest_matching_image, save_matching_flag, cds_status
	global camera_unseen

	# 食洗器の写真を撮影
	img   = _capture_washer(full_size=False)		# カラー
	img_g = cv2.cvtColor( img, cv2.COLOR_RGB2GRAY ) # グレー

	# まず、ドアの開閉状態（OPEN/CLOSE）をパターンマッチングで判定
	# OPEN/CLOSEの両方の相関係数を出して比較

	old_cds_status = cds_status

	if pi.read(CDS_PIN)==pigpio.HIGH:		# 明るい場合
		cds="明るい"
		cds_status = True
		result_cl = cv2.matchTemplate(img_g, temp_light_close, cv2.TM_CCOEFF_NORMED)
		result_op = cv2.matchTemplate(img_g, temp_light_open , cv2.TM_CCOEFF_NORMED)
		thr = TEMP_DAY_MATCHING_THRESHOLD
	else:									# 暗い場合
		cds="暗い"
		cds_status = False
		result_cl = cv2.matchTemplate(img_g, temp_dark_close, cv2.TM_CCOEFF_NORMED)
		result_op = cv2.matchTemplate(img_g, temp_dark_open	, cv2.TM_CCOEFF_NORMED)
		thr = TEMP_NIGHT_MATCHING_THRESHOLD

	# TODO: 前回とCDS状態が違うときは多頻度監視をリセットする！
	if cds_status != old_cds_status:
		_matching_washer.door_counter  = 0
		_matching_washer.timer_counter = 0

	# 開閉それぞれの相関値を得る
	_, corr_cl, _, maxLoc_cl = cv2.minMaxLoc(result_cl)
	_, corr_op, _, maxLoc_op = cv2.minMaxLoc(result_op)
	g.log( "1WASHER", f"CDS:{cds} / CL:{corr_cl:.2f} / OP:{corr_op:.2f}" )
	
	# OPEN/CLOSEのどちらか判別できないときは諦める
	# （ケース１）開閉どちらも閾値を下回る場合（人がカメラを邪魔している等）
	# （ケース２）開閉の差が小さすぎる場合（不鮮明な写真？）
	if max(corr_cl, corr_op) < thr or abs(corr_cl - corr_op) < 0.1:
		g.log("1WASHER", "判定不能（相関が低すぎる or 相関に差がない）")

		# 警報処理を追加（2024/3/3）
		#if camera_unseen==False:
		#	camera_unseen = True
		#	start_alert_unseen()
		return WASHER_STATUS_UNKNOWN, WASHER_STATUS_UNKNOWN

	# すでに見通し警報が鳴っていたら解除する
	if camera_unseen:
		g.log("MONITOR","見えない警報解除")
		camera_unseen = False
		stop_alert_unseen()


	# タイマーLED判定に移る	
	# ドアの開閉判定に合わせて、検査すべきタイマーLEDの領域を微調整
	if corr_cl>=corr_op:
		# CLOSE状態認識
		door = WASHER_DOOR_CLOSE
		timer2h_TL = maxLoc_cl[0]+23, maxLoc_cl[1]+14
		timer2h_BR = timer2h_TL[0]+6, timer2h_TL[1]+6
		timer4h_TL = maxLoc_cl[0]+23, maxLoc_cl[1]+8
		timer4h_BR = timer4h_TL[0]+6, timer4h_TL[1]+6
		buttons_tl = maxLoc_cl[0], maxLoc_cl[1]
		buttons_br = maxLoc_cl[0]+temp_light_close.shape[1], maxLoc_cl[1]+temp_light_close.shape[0]
	else:
		# OPEN状態認識
		door = WASHER_DOOR_OPEN
		timer2h_TL = maxLoc_op[0]+30, maxLoc_op[1]+16
		timer2h_BR = timer2h_TL[0]+6, timer2h_TL[1]+6
		timer4h_TL = maxLoc_op[0]+30, maxLoc_op[1]+8
		timer4h_BR = timer4h_TL[0]+6, timer4h_TL[1]+6
		buttons_tl = maxLoc_op[0], maxLoc_op[1]
		buttons_br = maxLoc_op[0]+temp_light_open.shape[1], maxLoc_op[1]+temp_light_open.shape[0]

	#タイマ2Hと4HそれぞれのLED位置が確定
	# 2Hと4HタイマーLEDの領域、赤の重さを算出
	# TODO: 今はRだけの平均値処理をしている模様
	# TODO: https://edaha-room.com/python_cv2_blightness/2935/
	box2 = img[ timer2h_TL[1]:timer2h_BR[1], timer2h_TL[0]:timer2h_BR[0] ]
	box4 = img[ timer4h_TL[1]:timer4h_BR[1], timer4h_TL[0]:timer4h_BR[0] ]

	# 方法１：R層の平均値
	# Tで向きを変える→２行目（GBRなのでR）→１次元化→平均値
	c2 = box2.T[2].flatten().mean()
	c4 = box4.T[2].flatten().mean()
	cr = max(c2, c4) / min(c2, c4)

	# 方法２：全画素平均値（黒よりは明るいだろう）
	#c2 = box2.T[0].flatten().mean() + box2.T[1].flatten().mean() + box2.T[2].flatten().mean()	
	#c4 = box4.T[0].flatten().mean() + box4.T[1].flatten().mean() + box4.T[2].flatten().mean()	

	g.log("1WASHER", f"T2:{c2:0.0f} / T4:{c4:0.0f} / CR:{cr:1.2f}")

	# メインディスプレイ用に３ボタン・4H・2Hの各認識フレームを描く
	cv2.rectangle(img, timer2h_TL, timer2h_BR, color=(255,255,0), thickness=1)
	cv2.rectangle(img, timer4h_TL, timer4h_BR, color=(255,255,0), thickness=1)
	cv2.rectangle(img, buttons_tl, buttons_br, color=(255,255,255), thickness=1)
	# TODO: グローバルで渡すより、こちらから能動的にupdateさせるべきでは？
	# TODO: imgを引数にして、update_displayに引き渡す方がよいと思われる
	newest_matching_image = img.copy()

	# デバッグ用に、検出結果画像を保存（1回だけ保存）
	if save_matching_flag:
		save_matching_flag = False
		cv2.imwrite(f"result_CL{corr_cl:.2f}_OP{corr_op:.2f}.png", img)


	# ようやくLED判定
	# ①高得点領域がある
	if (max(c2,c4) > TEMP_TIMER_LED_THRESHOLD) or (cr>1.5 and max(c2,c4)>20) :
		if cr>TEMP_TIMER_LED_RATIO_THREDHOLF:
			# どちらかだけが高得点
			timer = WASHER_TIMER_2H if c2>c4 else WASHER_TIMER_4H
		else:
			# 両方が高得点はエラー
			timer = WASHER_STATUS_UNKNOWN
			g.log("1WASHER", f"C2{c2:0.0f}/C4{c4:0.0f}　ともに高得点エラー")
	
	# ②高得点領域が無い
	else: timer = WASHER_TIMER_OFF

	g.log("1WASHER", f"一致検出（{_door(door)}/{_timer(timer)}）")
	return door, timer

# ------------------------------------------------------------------------------
# door/timer/dishesの値→名前変換
# 以前はif～elifの繰り返しだったが、辞書形式に変更
def _door(door:int)->str:
	return {
		WASHER_DOOR_CLOSE		:"CLOSE",
		WASHER_DOOR_OPEN		:"OPEN",
		WASHER_STATUS_UNKNOWN	: "UNKNOWN"
	}.get(door, "UNKNOWN")


def _timer(timer:int)->str:
	return {
		WASHER_TIMER_OFF		: "OFF",
		WASHER_TIMER_2H			: "2H",
		WASHER_TIMER_4H			: "4H",
		WASHER_STATUS_UNKNOWN	: "UNKNOWN"
	}.get(timer, "UNKNOWN")

def _dishes(dishes:int)->str:
	return {
		WASHER_DISHES_EMPTY			: "EMPTY",
		WASHER_DISHES_DIRTY			: "DIRTY",
		WASHER_DISHES_WASHED		: "WASHED",
		WASHER_DISHES_WASHED_EMPTY	: "WASHED-EMPTY",
		WASHER_STATUS_UNKNOWN		: "UNKNOWN"
	}.get(dishes, "UNKNOWN")

def door_status()->str:
	return _door(washer_door)

def timer_status()->str:
	return _timer(washer_timer)

def dishes_status()->str:
	return _dishes(washer_dishes)

def washer_status()->str:
	return _door(washer_door)+","+_timer(washer_timer)+","+_dishes(washer_dishes)

def washer_voices()->None:
	if   washer_door==WASHER_DOOR_CLOSE	: g.talk("do'awa sima'tteimasu")
	elif washer_door==WASHER_DOOR_OPEN	: g.talk("do'awa hira'iteimasu")
	else 								: g.talk("do'ano jou'taiga wakarimasen")
	time.sleep(0.5)

	if   washer_timer==WASHER_TIMER_2H	: g.talk("ta'ima-wa niji'kanni se'ttosareteimasu")
	elif washer_timer==WASHER_TIMER_4H	: g.talk("ta'ima-wa yoji'kanni se'ttosareteimasu")
	elif washer_timer==WASHER_TIMER_OFF	: g.talk("ta'ima-wa o'fudesu")
	else								: g.talk("ta'ima-no jou'taiga wakarimasen")
	time.sleep(0.5)

	if	 washer_dishes==WASHER_DISHES_EMPTY	: g.talk("shokki'wa kara'ppodesu")
	elif washer_dishes==WASHER_DISHES_DIRTY : g.talk("shokki'wa yogorete/ima'su")
	elif washer_dishes==WASHER_DISHES_WASHED: g.talk("shokki'wa senjouzumi/de'su")
	elif washer_dishes==WASHER_DISHES_WASHED_EMPTY: g.talk("shokki'wa senjouzumide toridasi/ma'sita")
	else									: g.talk("shokki'no jou'taiga wakarimasen")


# ------------------------------------------------------------------------------
def monitor_washer()->None:
	"""
	食洗器を撮影して、現在の状況を確認する
	数十秒ごとにタイマーでメインルーチンからコールされる

	メインルーチン（schedule)
	monitor_washer★			→ 過去の状態も踏まえ、DOOR/TIMER/DISHESを決める
	_matching_washer		→ one_washerの認識エラー対策で、頻度監視する
	_matching_one_washer	→ パターンマッチングでDOOR/TIMERを判定する
	_capture_washer			→ キャプチャーする
	

	TODO: 全然あってない↓	
	・下請け（_matching_washer）で現在の状態（ドア・タイマ）を調べる
	・状態がunknownなら終了
	・ドア開→汚れ食器あり
	・ドア閉→なにもしない
	・タイマーオフ→過去にタイマーセットされているなら、洗浄完了扱い
	・タイマーオン→汚れ食器なし
	"""
	global washer_dishes, washer_door, washer_timer
	global last_closed_door_time, need_to_notice_timer_set
	global camera_unseen

	start = datetime.datetime.now()		# 処理時間計測

	# 直前値を保持
	old_washer_dishes	= washer_dishes
	old_washer_door		= washer_door
	old_washer_timer	= washer_timer

	# １ショット撮影してドア・タイマの状態を獲得（頻度監視もしてくれる）
	door, timer = _matching_washer()

	# DOOR状態不明なら諦める（ガード節）
	# DOORが分からないなら、TIMERも分からないはずなので終了
	# TIMERだけのUNKNOWNを取り残さないように注意すべし
	if door==WASHER_STATUS_UNKNOWN:
		g.log("MONITOR", "判定不能")
		g.log("MONITOR", "")
		return
	
	# ここからは少なくともドア状態は見えている前提で各種処理に入る
	# 最新の状態をstatic変数に反映する
	washer_door  = door
	washer_timer = timer

	# ドア・タイマによるdishesの状態設定・アクション

	# ドアが閉まっている
	if door==WASHER_DOOR_CLOSE:
		# 最後にドアが閉まっていた時刻を記憶（更新）
		last_closed_door_time = datetime.datetime.now()

		# 「洗浄済み空っぽ」を確認した後の処理
		if washer_dishes == WASHER_DISHES_WASHED_EMPTY:
			washer_dishes = WASHER_DISHES_EMPTY

		# ドア閉で警報を鳴らす（１回だけ）
		if old_washer_door == WASHER_DOOR_OPEN:
			g.log("MONITOR", "ドアがしまりました")
			g.talk("do'aga sima'rimasita")
			if washer_timer==WASHER_TIMER_OFF:
				if washer_dishes==WASHER_DISHES_DIRTY:
					g.talk("ta'ima-no/se'ttowo wasure/na'i/dene'")
				elif washer_dishes==WASHER_DISHES_WASHED:
					g.talk("tori'dashi/wasu'reno na'iyouni kiwo'tuketekudasai")
			else:
				g.talk("ta'ima-wa settozumi/na'node ansinsite nema'shou.")

	# ドアが開いている
	else:
		# とりあえず開いた事実を告げる（検出後の最初の１回だけ、その後の処理は継続されるので注意！）
		if old_washer_door == WASHER_DOOR_CLOSE:
			g.talk("do'aga hira'kimasita")
			g.log("MONITOR", "ドアが開きました")

		# 食器は入っていない
		if washer_dishes==WASHER_DISHES_EMPTY:
			# 一定時間空けたなら、汚れた食器を入れたハズ
			if (datetime.datetime.now()-last_closed_door_time).seconds > DOOR_OPEN_CHECK_TIMER_s:
				# 食器ステータスを「汚れ」に
				washer_dishes = WASHER_DISHES_DIRTY
				g.log("MONITOR", "ドアが長時間開きました（EMPTY→DIRTY）")

				# まだタイマーをセットしてない
				if washer_timer==WASHER_TIMER_OFF:
					g.talk("ta'ima-no/se'ttowo wasurena'ide.")

					# 30分後には念のため確認開始（夜照明を消す前の事前チェックサービス）
					schedule.every(10).minutes.do(check_washer).tag("check_washer")

				# タイマーセット済み
				else:
					g.talk("do'awo sime'runowo wasurezuni.")


		# すでに食器が入っている
		elif washer_dishes==WASHER_DISHES_DIRTY:
			g.log("MONITOR", "ドア開放を検出（DIRTY）")
			# 音声は開けた時の１回だけ
			if old_washer_door == WASHER_DOOR_CLOSE and washer_timer==WASHER_TIMER_OFF:
				g.talk("ta'ima-no/se'ttowo wasurezuni.")

		# 洗浄済みの食器が入っている
		# 開けたということは、食器を取り出そうとしているタイミングのハズ
		else:
			g.log("MONITOR", "ドア開放を検出（WASHED）")

			# 最初からEMPTYなのと、WASHED→EMPTYになった場合の区別ができないので「タイマー忘れるな」警報につながる・・・。
			washer_dishes = WASHER_DISHES_WASHED_EMPTY	# 洗浄済みを確認した「空っぽ」

			# 音声は開けた時の１回だけ
			if old_washer_door == WASHER_DOOR_CLOSE:
				g.talk("shokki'wa ara'tte/arima'suyo.")
				start_alert_washed()

	# ドア処理終了
	# ここからタイマ状態の変化検出
	if timer!=WASHER_STATUS_UNKNOWN and old_washer_timer!=timer and old_washer_timer!=WASHER_STATUS_UNKNOWN:
		# 3.タイマーがオフ（直前までタイマONなら洗浄開始のハズ！！）
		if timer==WASHER_TIMER_OFF:
			g.log("MONITOR", "洗浄が始まりました")
			washer_dishes=WASHER_DISHES_WASHED

		# 4.タイマーが2hまたは4h（食器には直接の変化なし）
		if timer==WASHER_TIMER_2H or timer==WASHER_TIMER_4H:
			g.log("MONITOR","タイマーがセットされました")
			g.talk("ta'ima-ga se'tto/sare'masita.")
			g.talk("korede' hitoa'nsin de'su.")
			need_to_notice_timer_set = True

	g.log("MONITOR", f"食洗器チェック終了：{washer_status()} 【{(datetime.datetime.now()-start).seconds}秒】")
	g.log("MONITOR","")
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
	global need_to_notice_timer_set

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

		# タイマがセットされている→OK音声
		else:
			if need_to_notice_timer_set:
				# これ以降、音声通知の必要はなくなる
				need_to_notice_timer_set = False

				if call_from_child==False:
					# CDS感度過剰でここが大量にコールされてしまう・・・。
					# １晩で１回に制限したいところで、発声フラグを作るか？

					g.log("WASHER","食器が入っていて、タイマーはセットされています！")
					g.talk( "shokuse'nkiwa daijo'ubu desu.")
					#g.talk( "a'nsinsite oya'suminasai.")

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
	# タイマーがセットされている状態では、いちいち音声アラートはうるさいのでやらない

def stop_alert_timer_ok()->None:
	"""
	ボタンでダイアログ消したときの扱い
	"""
	g.log("TIMER","警報終了～")
#	g.talk("ke'ihou tei'si")
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
	# タイマーセット済みと同様、ここで音声アラートは過剰なのでカット
#	g.talk("shokki'wa ara'tte/ari'masuyo-")

def stop_alert_washed()->None:
	"""
	ボタンでダイアログ消したときの扱い
	"""
	g.log("TIMER","終了～")
	#g.talk("pipi")
	schedule.clear("alert_washed")
	schedule.clear("stop_alert_washed")
	g.update_display_immediately()

# ------------------------------------------------------------------------------
def start_alert_unseen()->None:
	"""
	カメラで食洗器の状態を検出できないときのアラート
	ひょっとすると、頻度監視してやった方がいいかもしれない
	"""
	g.log("MONITOR","見えない")
	alert_unseen()
	schedule.every(WASHER_UNSEEN_INTERVAL_s).seconds\
			.do(alert_unseen).tag("alert_unseen")

	schedule.every(WASHER_UNSEEN_TIMER_s).seconds\
			.do(stop_alert_unseen).tag("stop_alert_unseen")

def alert_unseen()->None:
	"""
	タイマーセット済みハンドラ～
	"""
	g.set_dialog(PIC_UNSEEN, stop_alert_unseen )
	g.log("MONITOR", "食洗器が見えないですよ～")
	g.talk("shokuse'nkiga mie'naizo-")

def stop_alert_unseen()->None:
	"""
	ボタンでダイアログ消したときの扱い
	"""
	g.log("MONITOR","警報終了～")
	g.talk("mie'ruyouni narima'sita")
	schedule.clear("alert_unseen")
	schedule.clear("stop_alert_unseen")
	g.update_display_immediately()

# ------------------------------------------------------------------------------
def preview_washser(min:int)->None:
	"""
	カメラのプレビューを表示する

	min: プレビューを自動終了する時間（分）

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

	# 開始時刻
	st = time.time()

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

		# ボタンで終了
		if g.front_button_status()==PUSH_1CLICK: break

		# タイマで終了
		if time.time()-st >= min*60: break

	# カメラを停める
	picam.stop()
	picam.close()

	# カメラを再起動
	init_camera()

	g.talk("ka'mera/cho'usei shuu'ryou")
	g.log("WASER","プレビュー終了")

	