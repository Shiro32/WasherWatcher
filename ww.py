#!usr/bin/env python
# -*- coding: utf-8 -*-

# 2024/11/12
#  食洗器監視装置（WasherWatcher）のメインコード
#
#　ww.py		:メイン処理（カメラ監視）＋表示（開閉・フラグ、時計、便利）
#  comm.py		: 通信関係（サーバー・クライアント両方）
#  cfg.py		: 定数・サブルーチン
#  globals.py	: グローバル変数（フル修飾でアクセス）
#
# Function
#　・雨降り通知機能は実装したいが、tweliteを配置する余裕がない→他のデバイスからもらう？
#
#
# History
# 2024/11/12 ようやく作り始める
#
#-------------- 表示モード ------------
# 1 NORMAL	標準状態（ドア開閉・食器予測・予約状態）
# 2 CLOCK	時計のみ
# 3 USEFUL	各種役立ち情報表示
# 4 DEVICE_INFO	装置の諸情報（IP、センサ状態など） 

# #--------------各種タイミング------------
#〇計測
#・MEASURE_INTERVAL	10秒
#・WET、BMEを計測。平均値計測用に足しこんだり、エラー処理も
#　
#
#〇画面更新
#・１秒（DISP_UPDATE_INTERVAL）
#・update_displayが共通で呼び出され、そこから４モードに分かれて描画
#・各モードの描画頻度は、update_display何回分かで決まる
#・その時点でのリングバッファに基づいて非同期に描画
#・最速で表示更新してほしいときは、update_display_immediatelyをcall
#
#〇時報
#・１時間おき
#・time_modeや、時間ごとの挨拶なども
#
#〇リアルタイム
#・天候チェック
#・モードＳＷ

print("起動開始！")

import sys
import time
import subprocess
import datetime
import random
from random import randrange as rnd
import schedule
import os
import ipget

print("公式import終了")

# 自作モジュールたち
from cfg import *   # 定数関係
import globals as g

import rain
import comm
import clock
import washer
import weather

g.log("MAIN", "各種import終了")

# ------------------------------------------------------------------------------
# 各種音声
voice_opening1		= "konnichiwa hana'tarou de'su"
voice_opening2		= "ju'nbi ka'nryou. ni'nmuwo kaisisimasu."

voice_shutdown1		= "gori'you ari'gatou goza'imasita."
voice_shutdown2		= "sui'cchiwo ki'runowo wasurezuni."
voice_shutdown3		= "mata'no gori'youwo oma'chisiteorimasu"

# ------------------------------------------------------------------------------
# 全体に共通のモード変数など
update_counter = 0									# 画面更新カウンタ（１分単位）
system_tick = 0
draw_normal_fujikyun_counter = 1000

# ステータスバーアイコン
PIC_DOOR_OPEN	= Image.open("icon/icon_unlock.png")
PIC_DOOR_CLOSE	= Image.open("icon/icon_lock.png")
PIC_TIMER_OFF	= Image.open("icon/icon_cancel.png")
PIC_TIMER_ON	= Image.open("icon/icon_clock.png")
PIC_DISHES_OK	= Image.open("icon/icon_smile.png")
PIC_DISHES_NG	= Image.open("icon/icon_radiation.png")


# ------------------------------------------------------------------------------
def update_display():
	"""画面更新のポータル

	schduleから一定間隔（10秒）で呼び出され、disp_modeに応じて各関数を呼び出す
	update_display_immediately経由で呼ばれた時は強制的に再描画（update_display_immediatelyはクリア）
	"""
	global update_counter, draw_normal_fujikyun_counter

	g.log("UPDATE DISPLAY", "counter:{}".format(update_counter))
	update_counter+=1

	# 即時更新フラグの扱い
	# TODO: 本当はgメソッドを使ってグローバル変数を直接たたきたくないが
	if g.update_display_immediately_flag :
		update_counter = 9999
		draw_normal_fujikyun_counter = 1000
		g.update_display_immediately_flag = False
	
	# 各画面モードに応じたメイン画面更新を行う
	# どれも表示バッファをクリアして、描画するところから始める
	if disp_mode==DISP_MODE_NORMAL and update_counter>=DISP_MODE_NORMAL_UPDATE_INTERVAL :
		g.clear_image(); update_counter = 0
		draw_normal()
	
	elif disp_mode==DISP_MODE_DEVICE_INFO and update_counter>=DISP_MODE_DEVICE_INFO_UPDATE_INTERVAL :
		g.clear_image(); update_counter = 0
		display_device_info()

	# 各モードの画面上に上書きされるダイアログの処理
	g.draw_dialog()


	# 全モード共通の作画を行う（ステータスバー、ドア・食器・予約表示）
	# 偽マックアイコン、時計表示など
	g.clear_sbar_image()
	g.image_sbar_buf.paste( SBAR_APPLE_ICON,  (30,0) )
	g.draw_sbar.line( (0, SBAR_HEIGHT-1, SBAR_WIDTH-1, SBAR_HEIGHT-1), fill="black", width=1 )

	# 時計（デカく書くようになったので不要）
#	g.draw_sbar.text( SBAR_CLOCK_POS, datetime.datetime.now().strftime("%H:%M"), fill="black", font=menu_font )

	# ドア・タイマ・食器
	x = 180
	if washer.washer_door == WASHER_DOOR_OPEN:
		g.image_sbar_buf.paste(PIC_DOOR_OPEN, (x, 1))
		x-=18
	
	if washer.washer_timer!=WASHER_TIMER_OFF:
		g.image_sbar_buf.paste(PIC_TIMER_ON, (x, 1))
		x-=18
	
	if washer.washer_dishes==WASHER_DISHES_DIRTY:
		g.image_sbar_buf.paste(PIC_DISHES_NG, (x, 1))

	# 各ウェザーモードでの追加描画（ポップアップ、雨・晴れアイコン）を行う
	rain.update_weather()

	g.epd_display()		# ディスプレイへのFLUSH

	# 最後にもう一回クリア！
	g.update_display_immediately_flag = False


# ------------------------------------------------------------------------------

draw_normal_old_fujikyun = ""


MAIN_UPPER_AREA			= (0,	0,		MAIN_WIDTH, 159		)
MAIN_LOWER_AREA			= (0,	165,	MAIN_WIDTH, MAIN_HEIGHT)

RAIN_ICON = Image.open("icon/mini_rain.png").resize((34,40))
TEMP_ICON = Image.open("icon/mini_temp.png").resize((34,40))

def draw_normal()->None:
	"""【モード1】ノーマル表示（水分量に応じて、ふじきゅんを描き分ける）
	・天気予報
	・ゴミの日
	・ドアなどは補足情報
	
	"""

	global draw_normal_fujikyun_counter, draw_normal_old_fujikyun

	g.log("DRAW_NORMAL", "begin")

	# 各領域を作る
#	g.draw_main.rectangle(MAIN_UPPER_AREA, 			fill=(150,150,255))
	g.draw_main.rectangle(MAIN_LOWER_AREA,			fill=(221,255,220))

	# 下半分に巨大時計
	dt = datetime.datetime.now()
	g.draw_main.text((3,20+160), dt.strftime("%H:%M"), font=clockLargeFont, fill="black")

	# ゴミ出し情報
#	gomi = Image.open("icon/gomi/gomi_plastic.png" ).resize((100,100))
#	g.image_main_buf.paste(gomi, (120+10,130+5), gomi)


	# 天気情報
	# 時刻によって、今日の天気か明日の天気を選ばないとあかん
	h = datetime.datetime.now().hour
	if h>=0 and h<  9: x=0 # 朝までは当日天気
	if h>=9 and h<=24: x=1 # 9時以降は翌日天気
	day, telop, img, day_rain, max_temp, min_temp = weather.get_forecast_weather(x)
	
	# 日付
	g.draw_main.text( (58 ,5), day, font=normal_font22, fill="black", anchor="ma")

	# 天気マーク＆キャプション
	tenki = Image.open(img).resize((100,100))
	g.image_main_buf.paste(tenki, (5,33), tenki)
	g.draw_main.text( (55,132), telop, font=normal_font16, fill="black", anchor="ma" )


	# 降水確率
	g.draw_main.rectangle((155, 0, MAIN_WIDTH	, 76), fill=(221,221,255))
	g.draw_main.rectangle((110, 0, 150			, 76), fill=(238,238,238))
	g.image_main_buf.paste(RAIN_ICON, (117,24), RAIN_ICON)

	if day_rain==100:
		g.draw_main.text((236, 18), "100"   , font=digital_font40	, fill="black", anchor="ra")
	else:
		g.draw_main.text((236, 12), day_rain, font=digital_font50	, fill="black", anchor="ra")
#	g.draw_main.text((228, 50), "%"		, font=normal_font14	, fill="black")

	## 気温
	g.draw_main.rectangle((110, 80	, 154		, 159), fill=(238,238,238))
	g.image_main_buf.paste(TEMP_ICON, (117,103), TEMP_ICON)
	## 最高気温（赤）最低気温（青）
	g.draw_main.rectangle((155,  80, MAIN_WIDTH, 118), fill=(255,0,0))
	g.draw_main.rectangle((155, 121, MAIN_WIDTH, 159), fill=(0,0,255))

	g.draw_main.text((220,  83), max_temp, font=digital_font30, anchor="ra", fill="white")
	g.draw_main.text((220, 126), min_temp, font=digital_font30, anchor="ra", fill="white")

#	g.draw_main.text( (120, 125+15), "昼", font=normal_font20, fill="black" )


STATUS_UPPER_AREA			= (0,	0,		MAIN_WIDTH, 159		)
STATUS_LOWER_AREA			= (0,	165,	MAIN_WIDTH, MAIN_HEIGHT)


# ------------------------------------------------------------------------------
def draw_washer_status()->None:
	"""【モード３】パターンマッチングの状況を詳細表示	
	"""

	g.log("DRAW_WASHER_STATUS", "begin")

	# 各領域を作る
#	g.draw_main.rectangle(MAIN_UPPER_AREA, 			fill=(150,150,255))
	g.draw_main.rectangle(MAIN_LOWER_AREA,			fill=(221,255,220))

# ------------------------------------------------------------------------------
(_dev_print_h, _dev_print_y) = (18,40)

def _print_one(label:str, msg:str):
	global _dev_print_y

	g.draw_main.text((0, _dev_print_y), f"{label:6s}:{msg}", font=normal_font20, fill="red")
#	g.draw_main.text( (0, _dev_print_y), "{:12}: {}".format(label,msg), font=info_content_font, fill="black" )
	_dev_print_y += _dev_print_h+5

def display_device_info():
	"""【モード4】デバイス情報表示
	"""
	g.log("draw_device", "begin")

	global _dev_print_y
	_dev_print_y = 150

	try:
		ip = ipget.ipget()
		msg =ip.ipaddr("wlan0")
	except:
		msg = "ネットワーク接続無し"

	# Pythonのせいで、コマンド中の"\"はエスケープして、"\\"にする必要があるので要注意
	command = "uptime | sed -r 's/.*up ([^,]*),.*/\\1/g'"
	proc = subprocess.Popen(
		command,
		shell  = True,                            #シェル経由($ sh -c "command")で実行。
		stdin  = subprocess.PIPE,                 #1
		stdout = subprocess.PIPE,                 #2
		stderr = subprocess.PIPE)                 #3

	res = proc.communicate()[0].decode("utf-8")	 #処理実行を待つ(†1)

	# 各情報を描いていく
	#g.draw_main.text( (0, 0), "【デバイス動作情報】", font=info_title_font, fill="black" )

	if type(washer.newest_matching_image)!=str:
		img = Image.fromarray(washer.newest_matching_image)
		img = img.resize( (img.width//2, img.height//2) )
		g.image_main_buf.paste( img )

	_print_one("NET"	, msg)
	_print_one("DOOR"	, washer.door_status())
	_print_one("TIMER"	, washer.timer_status())
	_print_one("DISHES"	, washer.dishes_status())

	#_print_one( "running"		, res )
	#_print_one( "network"		, msg )
	#_print_one( "SLIDE SW"		, str(pi.read(SLIDE_SW_PIN)) )
	#_print_one( "PIR"			, str(pi.read(PIR_PIN)) )
	#_print_one( "CDS"			, str(pi.read(CDS_PIN))	)
	#_print_one( "sleep mode"	, sleep_mode_label[g.sleep_mode] )
	#_print_one( "time mode"		, time_mode_label[g.time_mode] )
	#_print_one( "Weather GPIO"	,str( comm.check_rain_status() ) )
	#_print_one( "weather mode"	,weather_mode_label[rain.rain_mode] )
	#_print_one( "Weather GPIO"		, str(pi.read(RAIN_PIN)) )
	#_print_one( "weather mode"		, weather_mode_label[rain.rain_mode] )

#------------------------------------------------------------------------
# ここから先はサブルーチン的な処理
#------------------------------------------------------------------------

# ------------------------------------------------------------------------------
def init_at_boot()->None:
	"""各種初期化処理
	以前は関数の外側に書いていたがダサいので、関数化した
	それでも、グローバル変数の初期化などは各所に散らばってしまっている・・・。
	"""	
	global disp_mode

	disp_mode = DISP_MODE_NORMAL

	# スクリーンセーバー
	g.reset_screen_saver()
	g.setBackLight( g.EPD_BACKLIGHT_SW_MAIN, True )
	g.setBackLight( g.EPD_BACKLIGHT_SW_SAVER, True )

	# オープニング
#	g.talk( voice_opening1 )
	g.check_IP_address()

	# 各種自動実行のスケジューリング開始
	schedule.every(MONITOR_WASHER_INTERVAL_s).seconds	.do(washer.monitor_washer)
	schedule.every(DISP_UPDATE_INTERVAL_s).seconds		.do(update_display) # 画面更新（最短10秒）
	schedule.every().hour.at("00:00")					.do(rain.oclock)		# 時報処理
	schedule.every(LED_BLINK_INTERVAL_s).seconds		.do(g.handle_LED)		# フロントLED部リンク
	schedule.every().hour.at("00:00")					.do(weather.update_forecast_weather)
	weather.update_forecast_weather()

	# RAINの時計処理
	g.time_mode_check() # TODO: なんじゃこりゃ？

	# フロントボタンや背面各種スイッチの初期化
	g.init_front_button()
	g.init_switchs()

	# 通信回線
	comm.init_comm()

	# カメラ関係
	washer.init_washer()

	# 人感センサー電源（普通のGPIOからVSSを取っているので、HIGHにするのを忘れずに！）
	pi.write( PIR_VCC_PIN, pigpio.HIGH )

	# 初回描画は早めに（ちっとも早くならないけど）
	g.update_display_immediately()
#	g.talk( voice_opening2 )
	g.talk( "mai'do goriyo'u ari'gatou/goza'imasu." )

	#プレビュー
#	washer.preview_washser(min=5)
	g.reset_front_button_status()

# ------------------------------- main -------------------------------
if __name__ == "__main__":

	g.log("MAIN", "ようやく起動完了！")

	# まずは各種初期化を行う
	init_at_boot()

	# ここからメインルーチン
	try:
		while True:
			time.sleep(TIMER_TICK)  # 最小時間単位(50ms)
			system_tick += 1
			schedule.run_pending()

			# 人感センサーチェック（スクリーンセーバー解除）
			g.check_PIR()

			# ダイアログ表示時のボタン処理
			g.check_dialog()

			# お休みモード処理
			# 以前は過去の名残でrain内のチェックから呼び出していたがメインに移行
			g.check_sleep()

			# 雨チェックが頻繁過ぎるのでとりあえずオフ（2023/9/7）
			rain.check_weather()	# 雨降りチェック（tweliteのGPIOポーリングでやっている）

			# 画面更新を即時実施してもらいたい場合の処理
			# メインファイル（flower.py）以外から頼むときは、フラグでやっている # TODO: なんとかならんか？
			if( g.update_display_immediately_flag ):
				update_display()

			# 1クリック（警報なっていたら止めるとか）
			# 1クリック処理を引き受けそうな関数を呼び出してからクリア
			btn = g.front_button_status()

			if btn==PUSH_1CLICK:
				if g.dialog_status()==False:
					g.update_display_immediately()
#					g.front_button_sound()
					washer.washer_voices()
					g.reset_front_button_status()

			# ロングプレス（モードチェンジ）
			if btn==PUSH_LONGPRESS:
				g.front_button_sound()
				g.reset_front_button_status()

				# 現在の次のモードへ遷移
				disp_mode = [DISP_MODE_NORMAL, DISP_MODE_DEVICE_INFO][(disp_mode+1)%2]
				g.update_display_immediately()


			# 最長ロングプレス（電源オフ）
			if btn==PUSH_SUPER_LONGPRESS:
				# プレビュー
				washer.preview_washser()

			# スライドスイッチで電源を切るとするか・・・。
			if pi.read(SLIDE_SW_PIN)==pigpio.HIGH:
				g.talk( voice_shutdown1, True)
				g.clear_image()
				g.image_buf.paste( ICON_BYE_MAC, (0,0) )
				g.epd_display( False )

				g.log( "SHUTDOWN" )
				g.talk( voice_shutdown2, True )
				g.talk( voice_shutdown3, False )

				pi.stop()
				os.system( "sudo shutdown now" )
				sys.exit()


	except KeyboardInterrupt:
		print( "bye" )

	finally:
		pi.stop()
