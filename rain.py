#!usr/bin/env python
# -*- coding: utf-8 -*-

# 雨検出＆時報処理のモジュール
# もともと、〇〇太郎シリーズで使っていたものを、そのままWasherに移植
#
# TweliteのGPIOはそのままSocket通信で代用する
#
# 2024/11/26 Flower IoTから移植

import os
import time
import datetime
import pigpio
import random
from random import randrange as rnd

from cfg import *   # 定数関係
import globals as g # グローバル変数・関数
import weather

import comm

# --------------------- rain内のグローバル変数 ---------------------
rain_mode		= WEATHER_MODE_FINE
rain_counter	= 0	# 各モードの中で0からカウントし、1tickごとに増えるタイマ
rain_hours		= 0 # 長雨検出カウンタ。時報でカウントアップするので「何時間雨が続いているか」


# 時報関係
about_voice = ["ho'bo","oyoso'","da'itai","ho'bo","so'rosoro"]

# 長雨嘆き
long_rain_voice = [
	"a'me nakanaka yamanaidesune.", 
	"kyo'uwa zutto amedesune.", 
	"ha'yaku amega yamuto iidesune."]

# 晴れ
voices_hare = [
	"harede'suyo.",
	"harede'ngana.",
	"hare'yanen",
	"ha'retoru/ne'-",
	"mu'yamini osa'naidekudasai."
]

voices_rain = [
	"a'medesuyo.",
	"a'medengana.",
	"a'medesse",
	"a'medessharo.",
	"o'sisugiruto kowaremasuyo",
	"anmari osa'naidekudasai.",
	"a'meyanen"
]

voice_stop = "keihouwo teisi simasita."
voice_rain_start = "a'mega/fu'ttekimasita/yo sentakumono+o+torikomi'/masho'u"

# --------------------- 雨状態チェック ---------------------
# Twelightの状態を返すだけ
# 今現在、雨が降っているか（センサが濡れているか）だけ
# これをそのまま使って警報表示をやると渇き初めに頻発するので、タイマを持たせる
def is_rain()->bool:
	return True if comm.check_rain_status()==pigpio.LOW else False

# --------------------- ポップアップ ---------------------
# 雨降りはじめ・止んだ時のダイアログをポップアップさせる
# TODO: 実態は１種類のビットマップを貼っているだけだが・・・！？
def draw_dialog( s ):
#	g.image_main_buf.paste( DIALOG_BEGIN_ICON, (70,20) )
	g.image_main_buf.paste( ICON_RAIN, (10, 50) )

# ------------------------------------------------------------------------------
# 時報処理（音声）
# scheduleから毎正時に呼び出される
def oclock()->None:
	global rain_hours

	# まずは時刻（hour）をゲット
	h = datetime.datetime.now().hour

	g.time_mode_check()

	g.talk( about_voice[rnd(len(about_voice))]+"  <NUMK VAL="+str(h)+" COUNTER=ji>desu" )
	time.sleep(2)
	g.talk( "sabote'n no sui'bunryouwa <NUMK VAL="+str(int(g.newest_moist))+" COUNTER=pa-sento>desu." )

	if h==23:	g.talk( "mou nerujikan desune." )
	if h==15:	g.talk( "oya'tsuno jikan desune." )
	if h==12:	g.talk( "ohi'ru/ya'sumi de'sune." )
	if h==8:
#		g.talk( "tenkiyo'houwo otutaesimasu." )
		weather.check_weather_info(0, 0)

	# 日々の最大・最小データは夜中の3時でクリア
	if h==3:
		g.temp_min = g.hum_min = 100
		g.temp_max = g.hum_max = -100

	# 長雨をチェックする
	if not is_rain():
		rain_hours = 0
	else:
		rain_hours += 1 # １時間ごとにカウントアップ（長雨検出）
		if rain_hours >= TIMER_RAINTIME:
			g.talk( long_rain_voice[rnd(len(long_rain_voice))] )

# ------------------------------------------------------------------------------
# 【１】晴れモード（FINE）
# check: 　雨センサチェック、ボタン対応
# update:　晴れアイコン
def check_fine()->None:
	global rain_mode, sleep_timer

	# 雨センサチェック
	# 降雨側はタイマーなしで、必ず即発報させる（チャタリング防止はrain側で処理）
	if is_rain(): 
		rain_mode = WEATHER_MODE_BEGIN
		g.line_notify("花太郎：雨が降ってきましたよ！") # LINE通知
		return

	# RESETボタンを押したら、現在天気を喋る
	# TODO: ダイアログ消去と重複しないようにダサいチェックが入っている
	if g.dialog_status()==False and g.front_button_status()==PUSH_1CLICK:
		g.reset_front_button_status()
		g.talk(voices_hare[rnd(len(voices_hare))])
		g.update_display_immediately()
		sleep_timer = 999999

def update_fine()->None:
	# 雨が降ってないときの処理。たまには喋る？
	# mod = rain_counter % (TIMER_CLOCK+TIMER_WEATHER)
	pass
	#g.image_sbar_buf.paste( SBAR_WEATHER_ICON_FINE, SBAR_WEATHER_ICON_POS )

# ------------------------------------------------------------------------------
# 【２】降り始めモード（BEGIN）
# check: 　雨降り音声、強制画面更新、ボタン対応
# update:　雨アイコン、雨ポップアップ、LINE通知
def check_begin()->None:
	global rain_mode, sleep_timer

	# 数秒おきに「雨が降ってきた」音声
	if rain_counter % TIMER_RAIN_MESSAGE == 0:
		g.talk(voice_rain_start, wait=False)

	# タイムアップで、雨中モードへ。深夜帯は短めのタイマにする
	if g.time_mode< TIME_MODE_NIGHT and rain_counter>=TIMER_RAIN_BEGIN_ALERT : 		rain_mode = WEATHER_MODE_RAIN
	if g.time_mode>=TIME_MODE_NIGHT and rain_counter>=TIMER_RAIN_BEGIN_ALERT_SHORT:	rain_mode = WEATHER_MODE_RAIN

def end_begin()->None:
	global rain_mode, sleep_timer

	rain_mode = WEATHER_MODE_RAIN
	g.talk(voice_stop, True)
	sleep_timer = 999999
	g.update_display_immediately()

def update_begin()->None:
	# ステータスバーに加え、ポップアップも行う
	#g.image_sbar_buf.paste( SBAR_WEATHER_ICON_RAIN, SBAR_WEATHER_ICON_POS )
	g.set_dialog( ICON_RAIN, end_begin, "" )

# ------------------------------------------------------------------------------
# 【３】雨中モード（RAIN）
# check: 　雨センサチェック、ボタン対応
# update:　雨アイコン
def check_rain()->None:
	global rain_mode, sleep_timer

	# 雨センサチェック（降り始めから数十分はチャタリング防止で検査しない）
	# 晴れを検出したら、雨終了モードへ移行する
	if rain_counter>=TIMER_RAIN_MODE_CHATTERING and not is_rain():
		rain_mode = WEATHER_MODE_STOP
		g.line_notify("雨が止みましたよ！") # LINE通知

	# STOPボタンを押したら、現在天候をしゃべる
	# Thresholdのせいで、現在値と異なる場合があるのでちゃんとしゃべる
	# TODO: ダサい細工を何とかしたい
	if g.dialog_status()==False and g.front_button_status()==PUSH_1CLICK:
		g.reset_front_button_status()
		g.update_display_immediately()
		g.talk(voices_rain[rnd(len(voices_hare))] if is_rain() else "honto'uwa hare'desuyo")
		sleep_timer = 999999

def update_rain():
	pass
	#g.image_sbar_buf.paste( SBAR_WEATHER_ICON_RAIN, SBAR_WEATHER_ICON_POS )

# ------------------------------------------------------------------------------
# 【４】雨終了モード（STOP）
# check: 　雨止み音声、強制画面更新（不要か？）、ボタン対応
# update:　晴アイコン、晴ポップアップ、LINE通知
def check_stop()->None:
	global rain_mode, sleep_timer

	# 数秒おきに「雨がやんだよ」コール
	if rain_counter % TIMER_RAIN_MESSAGE == 0:
		g.talk("a'mega/yandamitaidesuyo?", wait=False)
		
	# 夜中は短めにする
	if g.time_mode< TIME_MODE_NIGHT and rain_counter>=TIMER_RAIN_STOP_ALERT      : rain_mode = WEATHER_MODE_FINE
	if g.time_mode>=TIME_MODE_NIGHT and rain_counter>=TIMER_RAIN_STOP_ALERT_SHORT: rain_mode = WEATHER_MODE_FINE

def end_stop()->None:
		global rain_mode, sleep_timer
		g.reset_front_button_status()
		rain_mode = WEATHER_MODE_FINE
		g.talk(voice_stop)
		sleep_timer = 999999

def update_stop():
	# ステータスバーに加え、ポップアップも行う
	#g.image_sbar_buf.paste( SBAR_WEATHER_ICON_FINE, SBAR_WEATHER_ICON_POS )
	g.set_dialog( PIC_RAIN, end_stop, "" )


# ------------------------------------------------------------------------------
# 天候情報の描画
# 画面モードでの描画（CO2グラフ）やステータスバーは完成しているので、
# 天候情報の追加を各天候モードに合わせて行う（1分毎くらいにコールされる）
# ★数分おきにしゃべるとか、そういう機能はcheckではなく、こちらのupdateに移管する
# 1.ステータスバーの描画
# 2.降り始め・降り終わりのポップアップ
#
def update_weather()->None:
	if rain_mode==WEATHER_MODE_FINE:	update_fine ()
	if rain_mode==WEATHER_MODE_BEGIN:	update_begin()
	if rain_mode==WEATHER_MODE_RAIN:	update_rain ()
	if rain_mode==WEATHER_MODE_STOP:	update_stop ()

# ------------------------------------------------------------------------------
# 天候状態の確認
# Tweliteの状態やタイマから、FINE/BEGIN/RAIN/STOPの４モードを判定する
# 画面描画はupdate_weather関数の方でやるので、ほとんど処理は無い
# 1. Tweliteのチェック
# 2. モード変更
# 3. 音声発信
# 4. 明暗状態（スリープモード）のチェック
def check_weather()->None:
	global rain_counter

	#お休みモード処理
	g.check_sleep()
	
	# 通常のメイン処理（モードによって４パターン）
	old_rain_mode = rain_mode

	# Switch-caseってできないのかねぇ・・・。
	if 		rain_mode==WEATHER_MODE_FINE:		check_fine()
	elif	rain_mode==WEATHER_MODE_BEGIN:		check_begin()
	elif	rain_mode==WEATHER_MODE_RAIN:		check_rain()
	elif	rain_mode==WEATHER_MODE_STOP:		check_stop()
	else:
		print("weather mode error")
		exit()

	rain_counter += 1

	# モードが変わったら、タイマリセット＆画面の即時更新
	if old_rain_mode != rain_mode:
		rain_counter = 0
		g.update_display_immediately()
