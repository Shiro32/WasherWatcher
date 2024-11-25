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

import sys
import time
import subprocess
import datetime
import random
from random import randrange as rnd


import schedule
import os
import requests # ThingSpeak用
import ipget

import traceback
import numpy as np

from cfg import *   # 定数関係
import globals as g
import comm
import clock

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
#	if disp_mode==DISP_MODE_NORMAL and update_counter>=DISP_MODE_NORMAL_UPDATE_INTERVAL :
#		g.clear_image(); update_counter = 0
#		draw_normal()
	
#	elif disp_mode==DISP_MODE_USEFUL and update_counter>=DISP_MODE_USEFUL_UPDATE_INTERVAL :
#		g.clear_image(); update_counter = 0
#		draw_mode4()

	if disp_mode==DISP_MODE_CLOCK and update_counter>=DISP_MODE_CLOCK_UPDATE_INTERVAL :
		g.clear_image(); update_counter = 0
		clock.draw_clock()

	elif disp_mode==DISP_MODE_DEVICE_INFO and update_counter>=DISP_MODE_DEVICE_INFO_UPDATE_INTERVAL :
		g.clear_image(); update_counter = 0
		display_device_info()

	# 各モードの画面上に上書きされるダイアログの処理
	g.draw_dialog()

	# 画面更新したときだけ、ステータスバーやウェザー情報を追加する
	# （ステータスバーやウェザーポップアップだけを行うケースが思いつかない）
	# TODO: 高頻度に描写してみる
	if update_counter==0 or True:
		# 全モード共通の作画を行う（ステータスバー、天気表示）
		# 偽マックアイコン、時計表示など
		g.clear_sbar_image()
		g.image_sbar_buf.paste( SBAR_APPLE_ICON,  (30,0) )
		g.draw_sbar.line( (0, SBAR_HEIGHT-1, SBAR_WIDTH-1, SBAR_HEIGHT-1), fill="black", width=1 )

#		g.draw_sbar.text( SBAR_MOIST_POS, "{0:3d}%".format(int(g.newest_moist)), fill="red", font=menu_font)

		# 時計または土壌
		g.draw_sbar.text( SBAR_CLOCK_POS, datetime.datetime.now().strftime("%H:%M"), fill="black", font=menu_font )
#		if( disp_mode!=DISP_MODE_CLOCK):
#			g.draw_sbar.text( SBAR_CLOCK_POS, datetime.datetime.now().strftime("%H:%M"), fill="black", font=menu_font )
#		else:
#			g.draw_sbar.text( SBAR_CLOCK_POS, "{0:.1f}°C".format(g.newest_temp), fill="black", font=menu_font )

		# 各ウェザーモードでの追加描画（ポップアップ、雨・晴れアイコン）を行う
#		rain.update_weather()

		g.epd_display()		# ディスプレイへのFLUSH

	# 最後にもう一回クリア！
	g.update_display_immediately_flag = False


# ------------------------------------------------------------------------------
_dev_print_h = 18
_dev_print_y = 40

def display_device_info():
	"""【モード4】デバイス情報表示
	"""
	g.log("draw_device", "begin")

	global _dev_print_y
	_dev_print_y = 15

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
	g.draw_main.text( (0, 0), "【デバイス動作情報】", font=info_title_font, fill="black" )

	_print_one( "running"		, res )
	_print_one( "network"		, msg )
	_print_one( "SLIDE SW"		, str(pi.read(SLIDE_SW_PIN)) )
	_print_one( "PIR"			, str(pi.read(PIR_PIN)) )
	_print_one( "CDS"			, str(pi.read(CDS_PIN))	)
	_print_one( "sleep mode"	, sleep_mode_label[g.sleep_mode] )
	_print_one( "time mode"		, time_mode_label[g.time_mode] )

	#_print_one( "Weather GPIO"		, str(pi.read(RAIN_PIN)) )
	#_print_one( "weather mode"		, weather_mode_label[rain.rain_mode] )

def _print_one(label:str, msg:str):
	global _dev_print_y

	g.draw_main.text( (0, _dev_print_y), "{:12}: {}".format(label,msg), font=info_content_font, fill="black" )
	_dev_print_y += _dev_print_h

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

	disp_mode = DISP_MODE_DEVICE_INFO

	# スクリーンセーバー
	g.reset_screen_saver()
	g.setBackLight( g.EPD_BACKLIGHT_SW_MAIN, True )
	g.setBackLight( g.EPD_BACKLIGHT_SW_SAVER, True )

	# オープニング
	g.talk( voice_opening1, TALK_FORCE )
	g.check_IP_address()

	# 各種自動実行のスケジューリング開始
#	schedule.every(5).seconds.do(m.check_soil_moist)									# 土壌水分抵抗
#	schedule.every(SENSING_INTERVAL_s)		.seconds.do(read_sensors)		# センサ計測

	schedule.every(DISP_UPDATE_INTERVAL_s).seconds.do(update_display) # 画面更新（最短10秒）
#	schedule.every().hour.at("00:00")							.do(rain.oclock)		# 時報処理
	schedule.every(LED_BLINK_INTERVAL_s)	.seconds.do(g.handle_LED)		# フロントLED部リンク

	# RAINの時計処理
	g.time_mode_check() # TODO: なんじゃこりゃ？

	# フロントボタンや背面各種スイッチの初期化
	g.init_front_button()
	g.init_switchs()

	# 初回描画は早めに（ちっとも早くならないけど）
	g.update_display_immediately()
	g.talk( voice_opening2, TALK_FORCE)
# ------------------------------- main -------------------------------
if __name__ == "__main__":

	init_at_boot()


	# ここからメインルーチン
	try:
		while True:
			time.sleep(TIMER_TICK)  # 最小時間単位
			system_tick += 1
			schedule.run_pending()

			# ダイアログ表示時のボタン処理
			g.check_dialog()

			# 画面更新を即時実施してもらいたい場合の処理
			# メインファイル（flower.py）以外から頼むときは、フラグでやっている # TODO: なんとかならんか？
			if( g.update_display_immediately_flag ):
				print("hoge")
				update_display()


			# 1クリック（警報なっていたら止めるとか）
			# 1クリック処理を引き受けそうな関数を呼び出してからクリア
			btn = g.front_button_status()

			if btn==PUSH_1CLICK:
				if g.dialog_status()==False:
					g.update_display_immediately()
					g.front_button_sound()
					g.reset_front_button_status()

			# ロングプレス（モードチェンジ）
			if btn==PUSH_LONGPRESS:
				g.front_button_sound()
				g.reset_front_button_status()

				# 現在の次のモードへ遷移
				disp_mode = [DISP_MODE_NORMAL, DISP_MODE_TREND, DISP_MODE_MODE4, DISP_MODE_CLOCK, DISP_MODE_DEVICE_INFO][(disp_mode+1)%5]
				g.update_display_immediately()

			## 超ロングプレス（省電力モード）
			#if btn==PUSH_SUPER_LONGPRESS:
			#	g.front_button_sound()
			#	g.reset_front_button_status()
			#	g.power_save_mode()

			# 最長ロングプレス（電源オフ）
			if btn==PUSH_SUPER_LONGPRESS:
				g.front_button_sound()
				g.reset_front_button_status()

				g.talk( voice_shutdown1, TALK_FORCE, True)
				g.clear_image()
				g.image_buf.paste( ICON_BYE_MAC, (0,0) )
				g.epd_display( False )

				g.log( "SHUTDOWN" )
				g.talk( voice_shutdown2, TALK_FORCE, True )
				g.talk( voice_shutdown3, TALK_FORCE, False )

				pi.stop()
				os.system( "sudo shutdown now" )
				sys.exit()

	except KeyboardInterrupt:
		print( "bye" )

	finally:
		pi.stop()
