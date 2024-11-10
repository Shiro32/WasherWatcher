#!usr/bin/env python
# -*- coding: utf-8 -*-

# 雨検出＆時報処理のモジュール
# 2022/9/27 雨警報頻発対策（タイマを設定）ただ短すぎただけみたい

import os
import time
import datetime
import pigpio
import random
from random import randrange as rnd

from cfg import *   # 定数関係
import globals as g # グローバル変数・関数

# --------------------- rain内のグローバル変数 ---------------------
rain_mode	= WEATHER_MODE_FINE
sleep_mode	= SLEEP_MODE_WAKEUP
sleep_timer	= 0

rain_counter 	= 0	# 各モードの中で0からカウントし、1tickごとに増えるタイマ
rain_hours		= 0 # 長雨検出カウンタ。時報でカウントアップするので「何時間雨が続いているか」

SLEEP_CHECK_INTERVAL = 60*5 / TIMER_TICK # 


# 時報関係
about_voice = ["ta'bun","oyoso'","da'itai","ho'bo","so'rosoro"]

long_rain_voice = [
	"a'me nakanaka yamanaidesune.", 
	"kyo'uwa zutto amedesune.", 
	"ha'yaku amega yamuto iidesune."]

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
voice_goodnight2		 = "akariwa kesiteokimasune."
voice_goodnight3		 = "soredewa oyasuminasai"

# 早く寝ろ
voice_nero = "ha'yaku ofu'ronihaitte nemashoune"

# 晴れ
voices_hare = [
	"harede'suyo.",
	"harede'ngana.",
	"mu'yamini osa'naidekudasai."
]

voice_stop = "keihouwo teisi simasita."
voice_rain_start = "a'mega/fu'ttekimasita/yo sentakumono+o+torikomi'/masho'u"

# --------------------- 雨状態チェック ---------------------
# Twelightの状態を返すだけ
# 今現在、雨が降っているか（センサが濡れているか）だけ
# これをそのまま使って警報表示をやると渇き初めに頻発するので、タイマを持たせる
def is_rain()->bool:
	return True if pi.read(RAIN_PIN)==pigpio.LOW else False

# --------------------- ポップアップ ---------------------
# 雨降りはじめ・止んだ時のダイアログをポップアップさせる
# TODO: 実態は１種類のビットマップを貼っているだけだが・・・！？
def draw_dialog( s ):
#	g.image_main_buf.paste( DIALOG_BEGIN_ICON, (70,20) )
	g.image_main_buf.paste( PIC_RAIN )

# ------------------------------------------------------------------------------
# 時報処理（音声）
# scheduleから毎正時に呼び出される
def oclock()->None:
	global rain_hours

	# まずは時刻（hour）をゲット
	h = datetime.datetime.now().hour

	time_mode_check()

	g.talk( about_voice[rnd(len(about_voice))]+"  <NUMK VAL="+str(h)+" COUNTER=ji>desu", TALK_MORNING )
	time.sleep(2)
	g.talk( "i'mawa <NUMK VAL="+str(int(g.newest_moist))+" COUNTER=pi'-pi-e'mu>desu.", TALK_MORNING )

	if h==23:	g.talk( "mou nerujikan desune.", TALK_FORCE )
	if h==15:	g.talk( "oya'tsuno jikan desune.", TALK_MORNING )
	if h==12:	g.talk( "ohi'ruyasumi desune.", TALK_MORNING )

	# 長雨をチェックする
	if not is_rain(): rain_hours = 0 ; return

	rain_hours += 1 # １時間ごとにカウントアップ（長雨検出）
	if rain_hours >= TIMER_RAINTIME:
		g.talk( long_rain_voice[rnd(len(long_rain_voice))], TALK_MORNING )

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
		g.line_notify("花太郎です。雨が降ってきましたよ！") # LINE通知

	# RESETボタンを押したら、現在天気を喋る
	# TODO: ダイアログ消去と重複しないようにダサいチェックが入っている
	if g.dialog_status()==False and g.front_button_status()==PUSH_1CLICK:
		g.reset_front_button_status()
		g.talk(voices_hare[rnd(len(voices_hare))], TALK_FORCE)
		sleep_timer = 999999

def update_fine()->None:
	# 雨が降ってないときの処理。たまには喋る？
	# mod = rain_counter % (TIMER_CLOCK+TIMER_WEATHER)
	g.image_sbar_buf.paste( SBAR_WEATHER_ICON_FINE, SBAR_WEATHER_ICON_POS )

# ------------------------------------------------------------------------------
# 【２】降り始めモード（BEGIN）
# check: 　雨降り音声、強制画面更新、ボタン対応
# update:　雨アイコン、雨ポップアップ、LINE通知
def check_begin()->None:
	global rain_mode, sleep_timer

	# 数秒おきに「雨が降ってきた」音声
	if rain_counter % TIMER_RAIN_MESSAGE == 0:
		g.talk(voice_rain_start, TALK_DAY, wait=False)

	# ストップボタンで、雨中モードへ切り替える
	if g.front_button_status()==PUSH_1CLICK:
		g.reset_front_button_status()
		rain_mode = WEATHER_MODE_RAIN
		g.talk(voice_stop, TALK_FORCE, True)
		sleep_timer = 999999

	# タイムアップで、雨中モードへ。深夜帯は短めのタイマにする
	if g.time_mode< TIME_MODE_NIGHT and rain_counter>=TIMER_RAIN_BEGIN_ALERT : 			rain_mode = WEATHER_MODE_RAIN
	if g.time_mode>=TIME_MODE_NIGHT and rain_counter>=TIMER_RAIN_BEGIN_ALERT_SHORT:	rain_mode = WEATHER_MODE_RAIN

def update_begin()->None:
	# ステータスバーに加え、ポップアップも行う
	g.image_sbar_buf.paste( SBAR_WEATHER_ICON_RAIN, SBAR_WEATHER_ICON_POS )
	draw_dialog( "RAIN!" )

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
		g.talk("a'medesuyo" if is_rain() else "honto'uwa hare'desuyo", TALK_FORCE)
		sleep_timer = 999999

def update_rain():
	g.image_sbar_buf.paste( SBAR_WEATHER_ICON_RAIN, SBAR_WEATHER_ICON_POS )

# ------------------------------------------------------------------------------
# 【４】雨終了モード（STOP）
# check: 　雨止み音声、強制画面更新（不要か？）、ボタン対応
# update:　晴アイコン、晴ポップアップ、LINE通知
def check_stop()->None:
	global rain_mode, sleep_timer

	# 数秒おきに「雨がやんだよ」コール
	if rain_counter % TIMER_RAIN_MESSAGE == 0:
		g.talk("a'mega/yandamitaidesuyo?", TALK_DAY, wait=False)

	# 雨終了モードをやめて、晴れモードへ切り替える
	if g.front_button_status()==PUSH_1CLICK:
		g.reset_front_button_status()
		rain_mode = WEATHER_MODE_FINE
		g.talk(voice_stop, TALK_FORCE)
		sleep_timer = 999999
		
	# 夜中は短めにする
	if g.time_mode< TIME_MODE_NIGHT and rain_counter>=TIMER_RAIN_STOP_ALERT      : rain_mode = WEATHER_MODE_FINE
	if g.time_mode>=TIME_MODE_NIGHT and rain_counter>=TIMER_RAIN_STOP_ALERT_SHORT: rain_mode = WEATHER_MODE_FINE

def update_stop():
	# ステータスバーに加え、ポップアップも行う
	g.image_sbar_buf.paste( SBAR_WEATHER_ICON_FINE, SBAR_WEATHER_ICON_POS )
	draw_dialog( "FINE!" )

# --------------------- スリープモードチェック ---------------------
# 単に夜間モードは輝度を下げてマナーモードにするだけだったが、
# 明るさに合わせていろいろ喋らせると楽しいので、徐々に充実中
# CDSセンサーで明るさを読み取って、at3011でしゃべらせる

def check_sleep()->None:
	global sleep_mode
	global sleep_timer

	old_sleep_mode = sleep_mode
	sleep_timer+=1

	# まずは多頻度防止用
	if sleep_timer < SLEEP_CHECK_INTERVAL: return

	# 時刻に応じた対応をするため
	h = datetime.datetime.now().hour

	# 明るい時の処理
	if pi.read(CDS_PIN)==pigpio.HIGH:
		# 直前が夜間モードで、明るくなった時だけ処理
		# 朝になった or 夜だけど照明をつけた
		if sleep_mode==SLEEP_MODE_SLEEP:

			# 夜に電気を付けた時
			if g.time_mode>=TIME_MODE_NIGHT:
				g.talk( "mo'u <NUMK VAL="+str(h)+" COUNTER=ji>desuyo'. "+ bright_voice[rnd(len(bright_voice))],  TALK_FORCE )

			# 普通に朝を迎えた場合→おはようございます
			elif g.time_mode<=TIME_MODE_MORNING:
				g.talk( voice_goodmorning1, TALK_FORCE )
				g.talk( voice_goodmorning_rain if is_rain() else voice_goodmorning_fine, TALK_FORCE)

			# 夜に部屋に入っただけ
			else:
				g.talk( mabushii_voice[rnd(len(mabushii_voice))], TALK_FORCE)

			sleep_timer = 0
			sleep_mode = SLEEP_MODE_WAKEUP

	# 暗い時の処理
	else:
		# 直前が昼間モードで、暗くなった時だけ処理
		# 電気を消した、自然に夜になった
		if sleep_mode==SLEEP_MODE_WAKEUP:
			time.sleep(3)

			# 寝るとき
			if g.time_mode >= TIME_MODE_SLEEP:
				g.talk( voice_goodnight1, TALK_FORCE )
				g.talk( voice_goodnight_rain if is_rain() else voice_goodnight_fine, TALK_FORCE )
				g.talk( voice_goodnight2, TALK_FORCE )
				g.talk( voice_goodnight3, TALK_FORCE )
			else:
				g.talk( voice_nero, TALK_FORCE )
				# トンネルモードを作りたい
			sleep_timer = 0
			sleep_mode = SLEEP_MODE_SLEEP

	# LEDの点灯制御
	# 夜間モードの時は最低輝度にする
	#if sleep_mode==SLEEP_MODE_WAKEUP:
	#	epd.turnOnBackLight()
	#else:
	#	epd.turnOffBackLight()

	g.setBackLight( EPD_BACKLIGHT_SW_MAIN, True if sleep_mode==SLEEP_MODE_WAKEUP else False )

#	epd.turnOnBackLight() if sleep_mode==SLEEP_MODE_WAKEUP else epd.turnOffBackLight()


def time_mode_check()->None:

	h = datetime.datetime.now().hour
	if( h>=TIME_MIDNIGHT and h<TIME_SUNRISE ):	g.time_mode = TIME_MODE_MIDNIGHT
	if( h>=TIME_SUNRISE and h<TIME_MORNING ):	g.time_mode = TIME_MODE_SUNRISE
	if( h>=TIME_MORNING and h<TIME_DAY ):		g.time_mode = TIME_MODE_MORNING
	if( h>=TIME_DAY and h<TIME_NIGHT):			g.time_mode = TIME_MODE_DAY
	if( h>=TIME_NIGHT and h<TIME_SLEEP):		g.gime_mode = TIME_MODE_NIGHT
	if( h>=TIME_SLEEP or h<TIME_MIDNIGHT):		g.time_mode = TIME_MODE_SLEEP

	g.log( "TIME MODE CHECK", str(g.time_mode) )

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
	check_sleep()
	
		# 通常のメイン処理（モードによって４パターン）
	old_rain_mode = rain_mode

	if rain_mode==WEATHER_MODE_FINE:		check_fine()
	elif rain_mode==WEATHER_MODE_BEGIN:	check_begin()
	elif rain_mode==WEATHER_MODE_RAIN:	check_rain()
	elif rain_mode==WEATHER_MODE_STOP:	check_stop()
	else:
		print("weather mode error")
		exit

	rain_counter += 1

	# モードが変わったら、タイマリセット＆画面の即時更新
	if old_rain_mode != rain_mode:
		rain_counter = 0
		g.update_immediately = True

