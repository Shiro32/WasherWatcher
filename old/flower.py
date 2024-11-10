#!usr/bin/env python
# -*- coding: utf-8 -*-

# 2023/6/20
#		mac型CO2計測装置から大部分を移植してスタート
#
#　flower.py：メイン処理＋水分表示（ノーマル、トレンド、４モード）
#  rain.py	：twelite関係全部
#  cfg.py 	:定数・サブルーチン
#  globals.py: グローバル変数（フル修飾でアクセス）
#
# 2023/6/25 GitHub管理へ移行、News機能を削除
# 2023/6/26 全体的に稼働状態へ
#
#-------------- 表示モード ------------
# 1 NORMAL		キャラクタ（ふじきゅん）で水分量を表示。ステータスバー活用もあり
# 2 TREND			水分量主体のグラフ
# 3 MODE4			４分割表示（水分、室温、湿度、気圧）
# 4 CLOCK			時計
# 5 DEVICE_INFO	装置の諸情報（IP、センサ状態など） 

# #--------------各種タイミング------------
#〇計測
#・MEASURE_INTERVAL	10秒
#・WET、BMEを計測。平均値計測用に足しこんだり、エラー処理も
#　
#〇記録
#・DATA_STORE_INTERVAL	6回（10秒×６＝１分）
#・リングバッファに、期間平均値を書き込む
#・結局、記録は１分値しか残らない
#
#〇画面更新
#・１秒（DISP_UPDATE_INTERVAL）
#・update_displayが共通で呼び出され、そこから５モードに分かれて描画
#・各モードの描画頻度は、update_display何回分かで決まる
#・その時点でのリングバッファに基づいて非同期に描画
#・最速で表示更新してほしいときは、update_display_immediatelyをcall
#
#
#〇ファイル書込
#・FILE_WRITE_INTERVAL	60秒
#
#〇時報
#・１時間おき
#・time_modeや、時間ごとの挨拶なども
#
#〇リアルタイム
#・天候チェック
#・レンジＳＷ
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
import ambient

from matplotlib.dates import DateFormatter
import matplotlib.ticker as ticker

import traceback
#from PIL import Image,ImageDraw,ImageFont
import numpy as np
import matplotlib
matplotlib.use("Agg") # CUIでMATPLOTLIBを使うための設定
import matplotlib.pyplot as plt
import matplotlib as mpl
from mpl_toolkits.axes_grid1 import Divider, Size # 追加
from mpl_toolkits.axes_grid1.mpl_axes import Axes # 追加
from matplotlib.dates import date2num
from bs4 import BeautifulSoup
import re

from cfg import *   # 定数関係
import globals as g

import rain
import clock
import moist as m

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

# --------------------- Graph Setup ---------------------
# 指定サイズのグラフを作る（意外と大変！）
fig = plt.figure( dpi=100, figsize=((MAIN_WIDTH-10)/100, MAIN_HEIGHT/100)  ) # 264×176 pixels
ax1 = fig.add_axes( [0.13, 0.12, 0.8, 0.75] )

#---Soil Wet
ax1.xaxis.set_major_locator(mpl.ticker.LinearLocator(4) )
ax1.tick_params("both", labelsize=7, pad=5, length=0)

ax1.yaxis.set_major_locator(mpl.ticker.MaxNLocator(integer=True))
ax1.set_ylim(MOIST_MIN, MOIST_MAX)

#--- TEMPARATURE, HUMIDITY
ax2 = ax1.twinx()
ax2.xaxis.set_major_locator(mpl.ticker.LinearLocator(4) )
ax2.tick_params("both", labelsize=8, pad=2, length=0)
ax2.set_ylim(TEMP_MIN, TEMP_MAX)

# グラフ関係の各種バッファを用意する
# 実際の要素サイズはinitで決める
time_log, moist_log, temp_log, hum_log, press_log = [],[],[],[],[]

graphXRange = GRAPH_RANGE_LENGTH_m
graph_interval = graph_size = graph_draw = 0
xticks = GRAPH_RANGE_TICKS

# ------------------------------------------------------------------------------
def init_record_buffer():
	""" 記録用リングバッファの初期化

	土壌水分・温度・湿度・気圧のバッファを初期化
	それぞれの計測時刻を表すtime_logも初期化
	"""
	global time_log, moist_log, temp_log, hum_log, press_log
	
	moist_log = [0]*RECORD_MAX
	temp_log	= [0]*RECORD_MAX
	hum_log		= [0]*RECORD_MAX
	press_log	= [0]*RECORD_MAX

	begin = datetime.datetime.now()
	time_log = [begin - datetime.timedelta(seconds=RECORD_INTERVAL_s*i) for i in range(RECORD_MAX)]

# ------------------------------------------------------------------------------
records=0; moists=0; temps=0; hums=0; presses=0

def read_sensors():
	"""WET、BMEセンサーからの読み込み

	複数回の計測を平均化するようために、
	バッファ更新は別関数にして、schduleで定期実行するように変更
	"""
	global moists, temps, hums, presses, records

	try:
		(temp,hum,press) = bme.get_value() # BME280	

	except:
		return
	
	else:
		temps+=temp; hums+=hum; presses+=press

		# SPI経由で土壌水分量をゲット
		# 適切なライブラリがなかったので、SPIDEVで直接ゲットする
		w = spi.xfer2( [0x68, 0x00] )
		moists += int( ( ((w[0]<<8) + w[1]) & 0x3FF ) / 10 )


		# 指定回数カウントしたら平均値を作る
		records += 1
		if records >= SENSING_AVERAGE_TIMES:
			g.newest_moist	= moists 	/ records
			g.newest_temp		= temps 	/ records
			g.newest_hum		= hums		/ records
			g.newest_press	= presses / records
			moists = temps = hums = presses = records = 0

			# 日々の最大・最小値の記録をチェック
			g.temp_min	= int( min( g.newest_temp, g.temp_min ) )
			g.temp_max	= int( max( g.newest_temp, g.temp_max ) )
			g.hum_min		= int( min( g.newest_hum , g.hum_min ) )
			g.hum_max		= int( max( g.newest_hum , g.hum_max ) )

			g.log( "SENSORS av", "{0:4}% / {1:.1f}c / {2:4.0f}hPa / {3:.0f}%RH".format(g.newest_moist, g.newest_temp, g.newest_press, g.newest_hum))

def record_sensors()->None:
	"""センサー値をリングバッファに格納する
	各センサーの最新の平均値をそれぞれのリングバッファに追加する
	グラフの１目盛りごとの時間が微妙（半端な秒数）なので、scheduleで非同期呼び出しに変更
	最大の過去秒数（12×60×60）をグラフ幅（200）で割った秒数
	"""

	del time_log[0], moist_log[0], temp_log[0], hum_log[0], press_log[0]

	time_log	.append(datetime.datetime.now())
	moist_log	.append(g.newest_moist)
	temp_log	.append(g.newest_temp)
	hum_log		.append(g.newest_hum)
	press_log	.append(g.newest_press)

	g.log( "STORE DATA", "success")

# ------------------------------------------------------------------------------

def update_display():
	"""画面更新のポータル

	schduleから一定間隔（10秒）で呼び出され、system_modeに応じて各関数を呼び出す
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
	if system_mode==SYSTEM_MODE_NORMAL and update_counter>=DISP_NORMAL_UPDATE_INTERVAL :
		g.clear_image(); update_counter = 0
		draw_normal()

	# トレンドグラフの負荷が非常に重い（時間がかかる）
	# TODO: 更新頻度をうんと下げるか、別スレッドにする必要あり
	elif system_mode==SYSTEM_MODE_TREND and update_counter>=DISP_TREND_UPDATE_INTERVAL :
		g.clear_image(); update_counter = 0
		draw_graph()
	
	elif system_mode==SYSTEM_MODE_MODE4 and update_counter>=SYSTEM_MODE4_UPDATE_INTERVAL :
		g.clear_image(); update_counter = 0
		draw_mode4()

	elif system_mode==SYSTEM_MODE_CLOCK and update_counter>=DISP_CLOCK_UPDATE_INTERVAL :
		g.clear_image(); update_counter = 0
		clock.draw_clock()

	elif system_mode==SYSTEM_MODE_DEVICE_INFO and update_counter>=DISP_DEVICE_INFO_UPDATE_INTERVAL :
		g.clear_image(); update_counter = 0
		display_device_info()

	# 各モードの画面上に上書きされるダイアログの処理（土壌・雨ダイアログ共通）
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

	# TODO: 土壌水分状態（乾燥、過湿潤）は必須
		g.draw_sbar.text( SBAR_MOIST_POS, "{0:3d}%".format(int(g.newest_moist)), fill="red", font=menu_font)

		# 時計または土壌
		if( system_mode!=SYSTEM_MODE_CLOCK):
			g.draw_sbar.text( SBAR_CLOCK_POS, datetime.datetime.now().strftime("%H:%M"), fill="black", font=menu_font )
		else:
			g.draw_sbar.text( SBAR_CLOCK_POS, "{0:.1f}°C".format(g.newest_temp), fill="black", font=menu_font )

		# 各ウェザーモードでの追加描画（ポップアップ、雨・晴れアイコン）を行う
		rain.update_weather()

		g.epd_display()		# ディスプレイへのFLUSH

	# 最後にもう一回クリア！
	g.update_display_immediately_flag = False

# ------------------------------------------------------------------------------

draw_normal_old_fujikyun = ""

def draw_normal()->None:
	"""【モード1】ノーマル表示（水分量に応じて、ふじきゅんを描き分ける）

	どうやって変化をつけるか・・・？
	水分量＞閾値　：　楽しそうな絵を数枚回す（呼ばれるたびにランダム？）
	水分量＜閾値　：　飢餓っぽい絵を数枚回す

	急速に水をもらった時の処理は、センサー側でupdate_display_immediatelyを呼ぶ？
	恒常的な湿潤ではなく、水をもらった感謝的なポップアップはどうする？
	update側で処理できるか？
	"""

	global draw_normal_fujikyun_counter, draw_normal_old_fujikyun

	g.log("draw_normal", "begin")

	draw_normal_fujikyun_counter+=1
	if( draw_normal_fujikyun_counter>FUJIKYUN_UPDATE_INTERVAL_t ):
		draw_normal_fujikyun_counter = 0

		if m.moist_status==m.MOIST_STATUS_NORMAL:	draw_normal_old_fujikyun = PICS_NORMAL[ rnd(len(PICS_NORMAL)) ]
		if m.moist_status==m.MOIST_STATUS_DRYING:	draw_normal_old_fujikyun = PIC_DRY3
		if m.moist_status==m.MOIST_STATUS_DRY:		draw_normal_old_fujikyun = PICS_DRY[ rnd(len(PICS_DRY)) ]
		if m.moist_status==m.MOIST_STATUS_WET:		draw_normal_old_fujikyun = PICS_WET[ rnd(len(PICS_WET)) ]


	g.image_main_buf.paste( draw_normal_old_fujikyun )

	# この後、四隅に数字などをチマチマ記載予定
	# TODO: 稼働状態を何らかの表示で示す必要あり？？
	# SBARもあるのでほどほどに
	# とりあえず土壌水分量を書いてみよう
	# 絵が見にくくなる・・・ので、たまにだけ描く？
	#g.draw_main.text( MODE_NORMAL_MOIST_POS, "{:3d}%".format(int(g.newest_moist)), "red", font=digitalLargeFont )

# ------------------------------------------------------------------------------
def draw_graph():
	"""【モード2】グラフ全体の描画（トレンドグラフ）	
	pltで描いて、強引に貼り付ける

	"""
	g.log("draw_graph", "begin")

	ax1.plot( time_log, moist_log, lw=2, color="#4040FF" )
	ax2.plot( time_log, temp_log,	 lw=2, color="red" )

	end = datetime.datetime.now() + datetime.timedelta(minutes=0)
	begin = end - datetime.timedelta(minutes=graphXRange)

	ax1.set_xlim(date2num([begin,end]))
	ax1.xaxis.set_ticklabels(xticks)

	plt.grid()

	# Matplotlib → ndarray → Pillow変換
	fig.canvas.draw()
	img = Image.fromarray( np.array(fig.canvas.renderer._renderer) )
	g.image_main_buf.paste(img)
	img.close()

	# 計測値を数字で描く
	# 湿潤、温度、湿度、気圧全部
	g.draw_main.text( HUM_CURRENT_POS		,str(int(g.newest_hum))+"Rh%"				,font=normalFont, fontweight="bold", fill="black" )
	g.draw_main.text( PRESS_CURRENT_POS	,str(int(g.newest_press))+"hPa"			,font=normalFont, fontweight="bold", fill="black" )
	g.draw_main.text( MOIST_CURRENT_POS	,str(int(g.newest_moist))+"W%"			,font=normalFont, fontweight="bold", fill="black" )
	g.draw_main.text( TEMP_CURRENT_POS	,str(int(g.newest_temp*10)/10)+"°C"	,font=normalFont, fontweight="bold", fill="black" )

	g.log("draw_graph", "end")

# ------------------------------------------------------------------------------
def draw_mode4():
	"""【モード3】4文字パターンの表示
	"""
	g.log("draw_4mode", "begin")

	# 横・縦の区切り線（縦線は微妙に中間ではない）
	g.draw_main.line((0								,MAIN_HEIGHT/2,MAIN_WIDTH			, MAIN_HEIGHT/2), fill=0, width=1)
	g.draw_main.line((MAIN_WIDTH/2-10	,0						,MAIN_WIDTH/2-10, MAIN_HEIGHT)	, fill=0, width=1)

	g.draw_main.rectangle((0							,0						,MAIN_WIDTH/2-10,MAIN_HEIGHT/2), fill=(150,150,255))
	g.draw_main.rectangle((MAIN_WIDTH/2-10,0						,MAIN_WIDTH			,MAIN_HEIGHT/2), fill=(255,150,150))
	g.draw_main.rectangle((0							,MAIN_HEIGHT/2,MAIN_WIDTH/2-10,MAIN_HEIGHT), fill=(150,255,150))
	g.draw_main.rectangle((MAIN_WIDTH/2-10,MAIN_HEIGHT/2,MAIN_WIDTH			,MAIN_HEIGHT), fill=(150,255,255))

	# 1.湿潤度合い
	g.draw_main.text(
		MODE2_MOIST_POS, "{:2d}".format(int(g.newest_moist)), font=digitalLargeFont,
		fill="black" if MOIST_THRESHOLD_DRY < g.newest_moist<MOIST_THRESHOLD_WET else "red" )

	t1 = int(g.newest_temp);	t2 = int((g.newest_temp-t1)*10)
	h1 = int(g.newest_hum); 	h2 = int((g.newest_hum-h1)*10)

	# 2.温度
	g.draw_main.text( (MODE2_TEMP_POS[0]+78, MODE2_TEMP_POS[1]+37), ".{:1d}".format(t2), 
		  font=digitalMiddleFont, fill="black" )
	g.draw_main.text( MODE2_TEMP_POS, "{:2d}".format(t1),
		  font=digitalLargeFont, fill="black" )
	# 最大・最小値
	g.draw_main.text( (MODE2_TEMP_POS[0]+0, MODE2_TEMP_POS[1]+73), "{:2d}/{:2d}".format(g.temp_max, g.temp_min), 
		  font=digitalSmallFont, fill="black" )

	# 3.湿度
	g.draw_main.text( MODE2_HUM_POS,	"{:2d}".format(h1),
		  font=digitalLargeFont, fill="black" )
	# 最大・最小値
	g.draw_main.text( (MODE2_HUM_POS[0]+0, MODE2_HUM_POS[1]+70), "{:2d}/{:2d}".format(g.hum_max, g.hum_min), 
		  font=digitalSmallFont, fill="black" )

	# 4.気圧
	g.draw_main.text( MODE2_PRESS_POS,"{:4d}".format(int(g.newest_press)),
		  font=digitalPressFont, fill="black" )

	g.draw_main.text( MODE2_MOIST_UNIT_POS,	"W%",	font=unitFont, fill="black" )
	g.draw_main.text( MODE2_TEMP_UNIT_POS,"°C"	,	font=unitFont, fill="black" )
	g.draw_main.text( MODE2_HUM_UNIT_POS,	"Rh%"	,	font=unitFont, fill="black" )
	g.draw_main.text( MODE2_PRESS_UNIT_POS,"hPa",	font=unitFont, fill="black" )


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

	# 無理やり感が漂うけど、起動時間（Linux uptimeから無理やり作る）
	#command = "uptime | sed -r 's/.*up..([^,]*)(,.*)/\\1/g'"	#！ここに実行したいコマンドを書く！

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

	_print_one( "running"					, res )
	_print_one( "network"					, msg )
	_print_one( "SOUND SW"				, str(pi.read(SOUND_SW_PIN)) )
	_print_one( "SAVER SW"				, str(pi.read(SAVER_SW_PIN)) )
	_print_one( "Light GPIO"			, str(pi.read(CDS_PIN))	)
	_print_one( "Weather GPIO"		, str(pi.read(RAIN_PIN)) )
	_print_one( "weather mode"		, weather_mode_label[rain.rain_mode] )
	_print_one( "sleep mode"			, sleep_mode_label[g.sleep_mode] )
	_print_one( "time mode"		 		, time_mode_label[g.time_mode] )
	_print_one( "moist mode"			, m.moist_mode_label[m.moist_status+2])
	_print_one( "sensor int."			, str(RECORD_INTERVAL_s) )
	_print_one( "moist log"				, str(len(moist_log)) )
	_print_one( "time log"				, str(len(time_log)) )

def _print_one(label:str, msg:str):
	global _dev_print_y

	g.draw_main.text( (0, _dev_print_y), "{:12}: {}".format(label,msg), font=info_content_font, fill="black" )
	_dev_print_y += _dev_print_h

#------------------------------------------------------------------------
# ここから先はサブルーチン的な処理
#------------------------------------------------------------------------

# ------------------------------------------------------------------------------
def send2ThingSpeak():
	"""ThingSpeakにデータを送る
	ネットワークが無い時に備え、Try/Exceptしておく
	"""
	global moist
	return  # TODO: 未実装です

	try:
		data = { 'api_key':THINGSPEAK_API_KEY, 'field1':g.newest_moist }
		response = requests.post( THINGSPEAK_URL, json=data )
	except:
		print( "no network." )

def send_ambient():
	global moist_log, temp_log, hum_log, press_log
	global amb

	try:
		ret = amb.send({'d1':moist_log[-1], 'd2':temp_log[-1], 'd3':hum_log[-1], 'd4':press_log[-1] })
		g.log("SEND AMBIENT", "OK")
	except:
		g.log("SEND AMBIENT", "NG")

# --------------------- File Record Setup ---------------------
#fname = datetime.datetime.now().strftime("log_%Y%m%d%H%M%S.csv")
#with open(fname, "a") as csv_file:
#	csv_file.write( "TIME,CO2,TEMP\n")

def write_log():
	"""	計測データの書き出し
	TODO: 現状、それどころじゃないので未実装
	"""
	global csv_file
	return  # TODO: これも未実装

	# 本当はここでも平均化処理★
	dt = datetime.datetime.now().strftime( "%Y-%m-%d %H:%M:%S" )

	with open( fname, "a" ) as csv_file:
		csv_file.write( dt+","+str(g.newest_moist)+", "+str(g.newest_temp)+"\n" )

# ------------------------------------------------------------------------------
def init_at_boot()->None:
	"""各種初期化処理
	以前は関数の外側に書いていたがダサいので、関数化した
	それでも、グローバル変数の初期化などは各所に散らばってしまっている・・・。
	"""	
	global system_mode

	system_mode = SYSTEM_MODE_TREND

	# スクリーンセーバー
	g.reset_screen_saver()
	g.setBackLight( g.EPD_BACKLIGHT_SW_MAIN, True )
	g.setBackLight( g.EPD_BACKLIGHT_SW_SAVER, True )

	# オープニング
	g.talk( voice_opening1, TALK_FORCE )
	g.check_IP_address()

	# 記録用バッファ初期化
	init_record_buffer()

	# 各種自動実行のスケジューリング開始
	schedule.every(5).seconds.do(m.check_soil_moist)									# 土壌水分抵抗
	schedule.every(SENSING_INTERVAL_s)		.seconds.do(read_sensors)		# センサ計測
	schedule.every(RECORD_INTERVAL_s)			.seconds.do(record_sensors)	# センサ用リングバッファ更新

#	schedule.every(FILE_WRITE_INTERVAL_s)	.seconds.do(write_log)			# ファイル記録
#	schedule.every(IOT_SEND_INTERVAL_s)		.seconds.do(send_ambient)		# IOTクラウド送信

	schedule.every(DISP_UPDATE_INTERVAL_s).seconds.do(update_display) # 画面更新（最短10秒）
	schedule.every().hour.at("00:00")							.do(rain.oclock)		# 時報処理
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

	#		check_soil_moist()	# 水分量チェック（乾燥・標準・過湿潤、ダイアログなど）

			# 雨チェックが頻繁過ぎるのでとりあえずオフ（2023/9/7）
			rain.check_weather()	# 雨降りチェック（tweliteのGPIOポーリングでやっている）

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
				system_mode = [SYSTEM_MODE_NORMAL, SYSTEM_MODE_TREND, SYSTEM_MODE_MODE4, SYSTEM_MODE_CLOCK, SYSTEM_MODE_DEVICE_INFO][(system_mode+1)%5]
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
