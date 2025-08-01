#!usr/bin/env python
# -*- coding: utf-8 -*-

# WasherWatcher用のグローバル変数・グローバル関数用記述ファイル
# 読み込み先のpyファイルでは、import globalsで全部読み込む
# アクセスには、globals.x
# 各ファイル共通で使うファイル（変更あり）はこの形式でアクセスしないと、
# 個別にインスタンスが作られてしまうのでまずいことになる（共有しない）
#
# 逆に、編集しない定数類は、cfg.pyに記載する（参照専用）

from turtle import update
from cfg import *
import serial
import datetime
import ipget
import os
from random import randrange as rnd
import schedule

# この辺のimportのプリコンパイルはできないものか？★
from PIL import Image, ImageDraw
import smbus
import time
bus = smbus.SMBus(1)


import washer
import comm

# --------------------- 明るさに応じたvoice ---------------------

# 夜間に明るくなったタイミング
bright_voice = [ 
	"ha'yaku nena'sai", 
	"mo'u netaho'uga i'idesuyo", 
	"yo'ikowa nemasho'u", 
	"uwa' mabushi'idesu" ]

# 夜まぶしい
mabushii_voice = [
	"uwa' mabushi'idesuyo",
	"gextu mabushi'idengana",
	"nanya mabushi'igana"
	]

# おはよう
voice_goodmorning1 = "oha'you gozaimasu"
voice_goodmorning_fine = "sotowa hare'desuyo"
voice_goodmorning_rain = "sotowa za'nnen nagara a'medesuyo"

# おやすみ
voice_goodnight1 = "kyo'umo ichinichi otsukaresamadegasu."
voice_goodnight_fine = "so'towa hare'desuyo  ashitamo hareruto i'idesune."
voice_goodnight_rain = "so'towa a'medesuyo  asita'wa hareruto i'idesune."
voice_goodnight2		 = "  sore'dewa oyasuminasai."

# 早く寝ろ
voice_nero = "ha'yaku ofu'ronihaitte nemashoune"

# 昼間に光変化
voice_kurai = "cho'tto kura'idengana"

# 時間帯
time_mode	= TIME_MODE_DAY	# 時間帯モード




# --------------------- twelite間の通信チェック関係 ---------------------

# EPDを即時更新するフラグ
# schduleもupdate_counterも無視してとにかく最速。１回限りでリセット
update_display_immediately_flag = False

def update_display_immediately():
	global update_display_immediately_flag
	update_display_immediately_flag = True

# --------------------- フロントボタン処理 ---------------------
# フロントボタン処理用
# 最初はポーリングで作ったが、あまりに反応が悪いのでpigpioのcallbackで実装し直す
# メイン処理のほうでは、front_button_status()をチェックすればよい
#	PUSH_NONE			: 何もしていない
# PUSH_PRESSING	: 押下継続中（使い道は無い）
# PUSH_1CLICK		: 通常の１クリック
# PUSH_LONGPRES	: 長押し（モードチェンジ）
# PUSH_ULTRA_LONGPRESS : 超長押し（シャットダウンなど）
#
# （注意）
# メイン処理のほうでは上記ステータスに応じた処理を実行する際は、
# 必ずreset_front_button_status()を呼んでPUSH_NONEに戻すこと
# ボタンが押しっぱなしになる or 次が押せなくなる

_front_button_status = PUSH_NONE
_button_begin_tick = 0

# ------------------------------------------------------------------------------
def cb_front_button_interrupt(gpio, level, tick):
	"""フロントプッシュボタンのコールバック関数
	メインの仕事を止めてしまわないように、pigpioの割り込みハンドラとして実装
	RAISING（リリース）とFALLING（押し込み）両方をキャッチする（EITHER_EDGE）

	チャタリング防止				→　set_glitch_filterでpigpioに丸投げ
	１クリック							→ GPIOのRAISE（リリース）割り込みで処理
	ロング・超ロングプレス	→ set_watchdogでタイムアウトさせて判定
	"""
	global _button_begin_tick, _front_button_status

	log( "BTN2", "interrupt(STATUS:"+str(_front_button_status)+"/LEVEL:"+str(level)+")" )

	# 1. ボタン押下（level=0）を検出
	if level==0 and _front_button_status==PUSH_NONE:
		_front_button_status = PUSH_PRESSING
		_button_begin_tick = tick
		pi.set_watchdog( FRONT_BTN_PIN, PUSH_LONGPRESS_TIME_ms )		# ロングプレス用watchdog開始（1s）
		return

	# 2. ボタンリリース（level=1）を検出
	if level==1:
		d = pigpio.tickDiff(_button_begin_tick, tick )
		pi.set_watchdog( FRONT_BTN_PIN, 0 )

		# 通常の１プッシュ
		if _front_button_status==PUSH_PRESSING:
			log( "BTN", "1CLICK" )
			_front_button_status = PUSH_1CLICK	# 単純１クリック判定
			short_wakeup()
		else:
			_front_button_status = PUSH_NONE		# ロングプレス後のリリース
		return

	# 3.watchdogでの検出（level=2）
	# ロングプレス（TIME1）はwatchdogで検出する
	if level==2:
		pi.set_watchdog( FRONT_BTN_PIN, 0 )
		d = pigpio.tickDiff(_button_begin_tick, tick)

		# ロングプレス（１回目のタイムアウト）
		if d<PUSH_SUPER_LONGPRESS_TIME_ms*1000:	# tickはμSなので注意！
			# いったんはロングプレスとするが、継続して超ロングプレスを監視
			log( "BTN", "LONGPRESS" )
			_front_button_status = PUSH_LONGPRESS
			pi.set_watchdog( FRONT_BTN_PIN, PUSH_SUPER_LONGPRESS_TIME_ms-PUSH_LONGPRESS_TIME_ms)
			short_wakeup()

		# 極ロングプレス（２回目のタイムアウト）
		else:
			log( "BTN", "SUPER LONGPRESS" )
			_front_button_status = PUSH_SUPER_LONGPRESS
			short_wakeup()

# ------------------------------------------------------------------------------
def reset_front_button_status()->None:
	"""フロントボタンのステータスをリセットする
	メイン側から明示的にcallしているが、自動処理できないか試行錯誤中
	TODO: PUSH_1CLICKやPUSH_LONGPRESSをセットしてから10秒後に自動リセットとか
	"""
	global _front_button_status
	_front_button_status = PUSH_NONE
# ------------------------------------------------------------------------------
def front_button_status()->int:
	"""フロントボタンのステータスを返す。
	ステータスを内部変数にしたいので、この関数を通してメインへ帰す
	"""
	return _front_button_status
# ------------------------------------------------------------------------------
def front_button_sound()->None:
	"""フロントボタンを押したときのサウンド処理
	・あちこちでボタン処理を行うことになったため、統一感を出す
	・callback内部で処理するには重すぎるので、通常処理に戻ってからコールする
	"""
	s = ""
	if _front_button_status==PUSH_1CLICK			: s = "pi'xtu"
	if _front_button_status==PUSH_LONGPRESS			: s = "pipi'xtu"
	if _front_button_status==PUSH_SUPER_LONGPRESS	: s = "pipipi'xtu"
	if _front_button_status==PUSH_ULTRA_LONGPRESS	: s = "pu'supusupusu"

	if s!="": talk(s)

# ------------------------------------------------------------------------------
def init_front_button()->None:
	"""フロントボタン関係の初期化処理
	・コールバックやチャタリング防止
	・LEDも
	"""
	pi.callback( FRONT_BTN_PIN, pigpio.EITHER_EDGE, cb_front_button_interrupt )
	pi.set_glitch_filter( FRONT_BTN_PIN, PUSH_GLITCH_TIME )	# チャタリング防止フィルタ
	pi.set_watchdog( FRONT_BTN_PIN, 0 )
	set_LED_mode( LED_BLINK_LONG )

def init_switchs()->None:
	"""背面スイッチのコールバック関数設定
	"""
#	pi.callback( SAVER_SW_PIN, pigpio.EITHER_EDGE, cb_saver_sw_interrupt )
#	pi.set_glitch_filter( SAVER_SW_PIN, PUSH_GLITCH_TIME )

#	pi.callback( SOUND_SW_PIN, pigpio.EITHER_EDGE, cb_sound_sw_interrupt )
#	pi.set_glitch_filter( SOUND_SW_PIN, PUSH_GLITCH_TIME )

# ----------------------------- 汎用ダイアログ関数登場 -----------------------------
#	set_dialog	: ダイアログ表示を開始させる
#	draw_dialog	:	ダイアログを実際に描画する（update_displayから呼ぶ）
#	stop_dialog	: ダイアログの表示をやめさせる
# check_dialog: フロントボタン押下による消去チェック
# dialog_status: ダイアログが表示されているかチェック

_dialog_show_flag 	= False
_dialog_btn_cb 			= None
_dialog_timeout_cb 	= None
_dialog_icon:Image.Image	# TODO: Imageのヌルポインタはどう表現する！？

def draw_dialog()->None:
	"""ダイアログを表示させる本体関数
	・update_display関数などから呼ばれて、メイン画面の真ん中にダイアログを出す
	"""
	if _dialog_show_flag:
		image_main_buf.paste( _dialog_icon, (int((EPD_WIDTH-_dialog_icon.width)/2) ,int(((EPD_HEIGHT-SBAR_HEIGHT)-_dialog_icon.height)/2)) )

def check_dialog()->None:
	"""ダイアログ表示中にフロントボタンを監視する
	・ボタンが押されたらサウンドと消去処理を行う
	・callback関数が指定されていたらそれも実行
	"""
	if _dialog_show_flag:

		# フロントボタンが押されたら消去処理を行う
		if front_button_status()==PUSH_1CLICK:
			front_button_sound()
			reset_front_button_status()

	 		# ボタン押下用callbackが設定されていたら対応する
			if _dialog_btn_cb: _dialog_btn_cb()

			stop_dialog()

def stop_dialog()->None:
	"""ダイアログの消去処理（終了処理）
	・終了時のcallbackが指定されていたが、実行する（あまり思いつかないが）
	"""
	global _dialog_show_flag, _dialog_icon, _dialog_btn_cb, _dialog_timeout_cb

	schedule.clear( "stop_dialog" )
	set_LED_mode( LED_OFF )

	# タイムアウトcallbackをやってあげる
	if _dialog_timeout_cb: _dialog_timeout_cb()

	_dialog_show_flag 	= False
	_dialog_btn_cb 			= None
	_dialog_timeout_cb 	= None
	update_display_immediately()

def set_dialog( icon:Image.Image, btn_cb=None, timeout_cb=None )->None:
	"""一定時間、ダイアログを表示できるようにセットする
	icon				: 表示してほしい絵のファイル名（相対パス）
	btn_cb			: ボタン押下時に呼び出すべきコースバック（呼び出し側で用意してもらう） 
	timeout_cb	: 消去時に呼び出すべきコールバック（呼び出し側で用意してもらう） 
	
	・update_displayでダイアログ表示を依頼するflagを立てる
	・一定時間表示するためのタイマをセットする（clear_dialogを呼ぶ）
	・すでにダイアログが出ていて重複（水分と雨など）した場合は、既出を消してから出す
	"""
	global _dialog_icon, _dialog_show_flag, _dialog_btn_cb, _dialog_timeout_cb

	# スクリーンセーバー解除（ダイアログが出たらとりあえず表示する）
	reset_screen_saver()

	## すでにダイアログが出ていた場合、先に消去する → いろいろ失敗したので保留中
	#if _dialog_show_flag:
	#	stop_dialog()

	_dialog_show_flag	= True
	_dialog_icon			= icon
	_dialog_btn_cb		= btn_cb
	_dialog_timeout_cb = timeout_cb

	# 一定時間後にhideするためのタイマ
	schedule.clear("stop_dialog")
	schedule.every(DIALOG_TIMER).seconds.do(stop_dialog).tag("stop_dialog")

	update_display_immediately()
	set_LED_mode( LED_ON )

	# とりあえず全速力で描画する
	draw_dialog()

def dialog_status()->bool:
	return _dialog_show_flag


# ------------------------------------------------------------------------------
# 前面のLED関係諸ルーチン
# 標準的な点灯・点滅パターン
# 夜間　　　：点灯（点滅だと気になる）
# セーブ中  ：点滅（電源断と勘違いされないため）
# ダイアログ：点灯

_front_led_status = LED_BLINK_LONG
_led_blink_counter = 0

def set_LED_mode( mode:int )->None:
	global _front_led_status
	_front_led_status = mode


def handle_LED()->None:
	"""LEDの恒常的処理ルーチン
	・scheduleから呼ばれる（点滅タイミングになるので1s）
	・ステータスを反映して、消灯・点滅・点灯を制御する
	"""
	global _led_blink_counter, _epd_backlight_sw

	# 夜は問答無用で点灯→まぶしいので消灯にする（2024/2/15）
	if _epd_backlight_sw[EPD_BACKLIGHT_SW_MAIN]==False:
		#_turn_on_LED()
		_turn_off_LED()
		return

	# スクリーンセーブ中は点滅
	if _front_led_status==LED_OFF:
		_turn_off_LED()

	elif _front_led_status==LED_ON:
		_turn_on_LED()

	elif _front_led_status==LED_BLINK_SHORT:
		_led_blink_counter+=1
		if _led_blink_counter % 2==0:
			_turn_on_LED()
		else:
			_turn_off_LED()

	elif _front_led_status==LED_BLINK_LONG:
		_led_blink_counter+=1
		if _led_blink_counter % 3==0:
			_turn_on_LED()
		else:
			_turn_off_LED()


def _turn_on_LED()->None:
	"""LEDを点灯させる（GPIO出力して実際にHW処理する）
	"""
	pi.write( FRONT_LED_PIN, pigpio.HIGH )

def _turn_off_LED()->None:
	"""LEDを消灯させる（GPIO出力して実際にHW処理する）
	"""
	pi.write( FRONT_LED_PIN, pigpio.LOW )

# ------------------------------------------------------------------------------
# 人感センサー関係
# 誤検出がそこそこあるので、一定時間で一度でもONになったONとする処理

pir_on_count = pir_check_count = 0

def check_PIR()->None:
	global pir_check_count, pir_on_count

	pir_check_count+=1
	pir_on_count+=pi.read( PIR_PIN )

	if pir_check_count>50:
		#log( "PIR", f"ON:{pir_on_count}/{pir_check_count}" )
		if pir_on_count / pir_check_count > PIR_THRESHOLD:
			short_wakeup()
			reset_screen_saver()
		
		pir_check_count = pir_on_count = 0


# ------------------------------------------------------------------------------
# スクリーンセーバー関係

def reset_screen_saver()->None:
	"""スクリーンセーバーの新規セット
	名前が変だけど、スクリーンセーバーを解除して画面表示を再開するということ

	スクリーンセーバーをセットするということはこんなケース
	・起動時（init_at_boot）
	・声を出す（talk）
	・ボタンを押す（cb_front_button_interrupt）
	・ダイアログを出す（set_dialog）
	・スクリーンセーバースイッチをONにする
	・人感センサーがON（ONである限りずっと点灯）
	"""
	setBackLight( EPD_BACKLIGHT_SW_SAVER, True )	# 画面点灯
	set_LED_mode( LED_BLINK_LONG )

	# タイマの再セット
	_cancel_screen_saver_timer()
	schedule.every(SCREEN_SAVER_TIMER_m).minutes.do(_do_screen_saver).tag("_do_screen_saver")

def _do_screen_saver()->None:
	""" スクリーンセーバー状態への突入（画面を消すだけ）
	"""
	_cancel_screen_saver_timer()

	setBackLight( EPD_BACKLIGHT_SW_SAVER, False )	
	set_LED_mode( LED_BLINK_SHORT )

def _cancel_screen_saver_timer()->None:
	schedule.clear("_do_screen_saver")

# ------------------------------------------------------------------------------
# LCD画面用各種グローバル変数

# イメージバッファ（メイン画面とステータスバーに分ける）
image_buf 			= Image.new("RGB", (EPD_WIDTH, EPD_HEIGHT), "white" )
image_sbar_buf	= Image.new("RGB", (SBAR_WIDTH, SBAR_HEIGHT), "white" )
image_main_buf	= Image.new("RGB", (MAIN_WIDTH, MAIN_HEIGHT), "white" )
draw_sbar				= ImageDraw.Draw(image_sbar_buf)
draw_main				= ImageDraw.Draw(image_main_buf)

# バックライト制御用
# 全部Trueになって初めてONにする
_epd_backlight_sw	= [True, True] # 0:夜間対応、1:スクリーンセーバー
_screen_saving_flag = False	# スクリーンセーバー動作中＝True

# ------------------------------------------------------------------------------
# e-ink用イメージバッファのクリア
def clear_image():
	global image_buf
	image_buf = Image.new("RGB", (EPD_WIDTH, EPD_HEIGHT), "white" )
	draw_sbar.rectangle( (0, -1, SBAR_WIDTH, SBAR_HEIGHT+1), "white" )
	draw_main.rectangle( (0, -1, MAIN_WIDTH, MAIN_HEIGHT+1), "white" )

def clear_sbar_image()->None:
	draw_sbar.rectangle( (0, -1, SBAR_WIDTH, SBAR_HEIGHT+1), "white" )
	
# ------------------------------------------------------------------------------
# e-ink画面の更新
# ただ、Imageバッファをepd（実際にはOLED）に転送するだけ
def epd_display( concat=True ):
	if concat:
		# イメージバッファを結合する
		image_buf.paste(image_sbar_buf, (0, 0) )
		image_buf.paste(image_main_buf, (0, SBAR_HEIGHT) )

	epd.ShowImage( image_buf.rotate(0) )

def handleBackLight()->None:
	global _screen_saving_flag

	# _epd_baklight_swの全要素がONの時だけ点灯する
	for f in _epd_backlight_sw:
		if f==False :
			_screen_saving_flag = True
			epd.turnOffBackLight()
			return

	_screen_saving_flag = False
	epd.turnOnBackLight()

def setBackLight( level:int, mode:bool )->None:
	"""バックライトの制御
	以下のAND処理を行う
	・時間帯によるON/OFF
	・スクリーンセーバーによるON/OFF
	"""
	global _epd_backlight_sw

	_epd_backlight_sw[level] = mode
	handleBackLight()

# --------------------- TALK ICでしゃべる ---------------------
# wait
#   True: 喋り終わるまで待つ（デフォルト）
#   False: 待たない
#
# ほとんどすべての依頼元が自国チェックをしていなかったので、
# ここで深夜にしゃべらないように改修する（2025/08/01）  

def cb_sound_sw_interrupt(gpio, level, tick)->None:
	"""サウンドSWの割り込み処理ハンドラ"""
	talk( "saundowo o'n/nisi'masita." if level==0 else "saundowo o'fu/nisi'masita." )

def talk(message, wait=True):
	# スクリーンセーバー解除
	# 音声SWをオフにしていても解除するかは賛否両論か・・・？
	reset_screen_saver()

#	if pi.read(SLIDE_SW_PIN)==pigpio.HIGH : return

	# 深夜帯うるさい対策登場！（2025/8/1）
	h = datetime.datetime.now().hour
	if 1<h<6: return

	# いよいよ喋るけど、まれにエラーが出るのでtry/catch
	try:
		uart=serial.Serial('/dev/ttyS0', 9600, timeout=10)
		uart.write(bytes(message+"\r\n","ascii"))

		# しゃべり終わるまで待つ（New!）
		if( wait==False ): return
		while True:
			rx = uart.read()
			status = rx.decode("utf-8")
			if( status==">"): break
	finally:
		return

def rndtalk(messages, wait=True):
	"""複数の文字レスリストの中の一つを乱数で選んでしゃべる
	"""
	talk( messages[rnd(len(messages))], wait )

def talks( messages )->None:
	"""複数のメッセージを連続して喋らせる
	　・メッセージーは引数messagesにリストの形で引き渡す。あまり意味ないか？
	"""
	for mes in messages:
		talk( mes, True )

# --------------------- log画面出力 ---------------------
def log(msg1, msg2=""):
	dt = datetime.datetime.now().strftime("%m/%d %H:%M:%S")
	print( "{0}【{1:15s}】{2}".format(dt, msg1, msg2) )

# ------------------------------------------------------------------------------
def check_IP_address():
	# 関係ないんだけど、実行ファイル名の取得・表示
	fn = "file :"+__file__
	md = datetime.datetime.fromtimestamp(os.path.getmtime(__file__)).strftime("build : %Y-%m-%d %H:%M:%S")

	w, h = normalFont.getsize(fn)

	try:
		ip = ipget.ipget()
		msg = ip.ipaddr("wlan0")
	except:
		msg = "no network."
	finally:
		draw_main.text( (0, h*0), "Welcome,now bootinimage_..", font=normalFont, fill=0)
		draw_main.text( (0, h*2), fn,  font=normalFont, fill=0)
		draw_main.text( (0, h*3), md, font=normalFont, fill= 0)
		draw_main.text( (0, h*4), "IP adr :"+msg,  font=normalFont, fill=0)
		epd_display()

# ----------------------------- Line Notice Setup ------------------------------
# メッセージをLINEで通知する
# 事前に、LINE TOKENを入手して設定しておくこと（cfgファイル）
def line_notify(msg):
	dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S : ")

	payload = {'message': dt+msg}
	url = 'https://notify-api.line.me/api/notify'
	headers = {'Authorization': 'Bearer ' + LINE_TOKEN}

	try:
		res = requests.post(url, data=payload, headers=headers)
	finally:
		return

# --------------------- スリープモードチェック ---------------------
# 単に夜間モードは輝度を下げてマナーモードにするだけだったが、
# 明るさに合わせていろいろ喋らせると楽しいので、徐々に充実中
# CDSセンサーで明るさを読み取って、at3011でしゃべらせる
# メインルーチンから1tick（50ms）ごとに高頻度で呼び出される

sleep_mode	= SLEEP_MODE_WAKEUP
SLEEP_CHECK_FREQ = 2/TIMER_TICK

def short_wakeup()->None:
	global sleep_mode

	sleep_mode = SLEEP_MODE_WAKEUP
	reset_screen_saver()
	setBackLight( EPD_BACKLIGHT_SW_MAIN, True )

def check_sleep_immediately()->None:
	check_sleep(True)


def check_sleep( check_now:bool=False )->None:
	global sleep_mode

	# まず、現在のCDSを読み込む
	cds = pi.read(CDS_PIN)

	# 多頻度監視機構をバイパス
	if check_now:
		# 強制的に現在計測値にしてしまう
		check_sleep.prev_cds 	= cds
		check_sleep.current_cds = cds
		check_sleep.counter 	= 0

	else:
		# 不安定なCDSの多頻度監視機構（washerのドア・タイマと同じ仕組み）
		# 前回と同じ値なら頻度UP
		if cds == check_sleep.prev_cds:
			check_sleep.counter += 1

			# 頻度が閾値を超えたら状態変化させる
			if check_sleep.counter >= SLEEP_CHECK_FREQ:
				check_sleep.current_cds = cds

			# 前回と異なる状態なら頻度を０にリセット
			# prevは変えるけど、currentはそのまま維持
			else:
				check_sleep.counter 	= 0
				check_sleep.prev_cds 	= cds

	# 時刻に応じた対応をするため
	h = datetime.datetime.now().hour

	# 明るい時の処理
	if check_sleep.current_cds == pigpio.HIGH:
		# 直前が夜間モードで、明るくなった時だけ処理
		# 朝になった or 夜だけど照明をつけた
		if sleep_mode==SLEEP_MODE_SLEEP:

			# 夜に電気を付けた時
			if time_mode>=TIME_MODE_NIGHT:
				talk( "mo'u <NUMK VAL="+str(h)+" COUNTER=ji>desuyo'. "+ bright_voice[rnd(len(bright_voice))]  )

			# 普通に朝を迎えた場合→おはようございます
			elif time_mode<=TIME_MODE_MORNING:
				talk( voice_goodmorning1 )
#				talk( voice_goodmorning_rain if is_rain() else voice_goodmorning_fine)

			# 夜に部屋に入っただけ
			else:
				talk( mabushii_voice[rnd(len(mabushii_voice))] )

			sleep_mode = SLEEP_MODE_WAKEUP
			reset_screen_saver()

	# 暗い時の処理
	else:
		# 直前が昼間モードで、暗くなった時だけ処理
		# 電気を消した、自然に夜になった
		if sleep_mode==SLEEP_MODE_WAKEUP:
			time.sleep(1)

			# 寝るとき
			if time_mode >= TIME_MODE_SLEEP:
				if washer.check_washer( call_from_child=False ):
					# 食洗器に問題がない時だけお休みあいさつ
					talk( "oyasuminasai" )
	#				talk( voice_goodnight1 )
	#				talk( voice_goodnight_rain if is_rain() else voice_goodnight_fine )
	#				talk( voice_goodnight2 )
			elif time_mode == TIME_MODE_DAY:
				#talk( voice_kurai )
				pass
			else:
				talk( voice_nero )

			sleep_mode = SLEEP_MODE_SLEEP

	setBackLight( EPD_BACKLIGHT_SW_MAIN, True if sleep_mode==SLEEP_MODE_WAKEUP else False )

# check_sleepの中で使うstatic変数。CDSの多頻度監視用に前値を保持しておく
check_sleep.prev_cds	= pigpio.HIGH
check_sleep.current_cds	= pigpio.HIGH
check_sleep.counter = 0


def time_mode_check()->None:
	"""
	時間帯（time_mode）を決める
	rainのoclock関数から呼ばれる"""

	global time_mode

	h = datetime.datetime.now().hour
	if( TIME_MIDNIGHT	<=h< TIME_SUNRISE ): time_mode = TIME_MODE_MIDNIGHT
	if( TIME_SUNRISE	<=h< TIME_MORNING ): time_mode = TIME_MODE_SUNRISE
	if( TIME_MORNING	<=h< TIME_DAY			): time_mode = TIME_MODE_MORNING
	if( TIME_DAY			<=h< TIME_NIGHT		): time_mode = TIME_MODE_DAY
	if( TIME_NIGHT		<=h< TIME_SLEEP		): time_mode = TIME_MODE_NIGHT
	if( h>=TIME_SLEEP or h<TIME_MIDNIGHT): time_mode = TIME_MODE_SLEEP

	log( "TIME MODE CHECK", str(time_mode) )


def is_rain()->bool:
	return True if comm.check_rain_status()==pigpio.LOW else False


