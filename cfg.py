#!usr/bin/env python
# -*- coding: utf-8 -*-

# WasherWatcher用の定数・グローバル変数・サブルーチン集
# 読み込み先のpyファイルでは、from cfg import *　で全部読み込む
#
# 〇定数（SW_PINなど）
# 〇デバイスオブジェクト（pi, epd, bmeなど）
# 〇サブルーチン
# ×編集可能なglobal変数はここに書かない→globals.pyへ


# 変数定義のために先に読み込む
from PIL import Image,ImageDraw,ImageFont

# --------------------- GPIOピン Setup ---------------------

#TODO:正しい値に★

FRONT_BTN_PIN	= 13		# いろいろ使うメインボタン
FRONT_LED_PIN	= 12	# 前面のLED
SLIDE_SW_PIN	= 18	# 背面のスライドスイッチ（音声？）

# センサー
CDS_PIN			= 20	# 明暗検出CDSのGPIOピン(in)
PIR_PIN			= 21	# 人感センサーピン


# --------------------- すべてのタイマ基準の元祖 ---------------------
TIMER_TICK		= 0.05	# タイムの最小単位。メインループのsleep値なので微妙

LED_OFF					= 0
LED_ON					= 1
LED_BLINK_SHORT = 2
LED_BLINK_LONG	= 3

# --------------------- フロントボタン関係のタイマ ---------------------
# 各種タイマ（マイクロセカンド単位）
PUSH_LONGPRESS_TIME_ms			= 1  * 1000 # 1秒
PUSH_SUPER_LONGPRESS_TIME_ms	= 6  * 1000 # 10秒（これだけmsなので注意）
LED_BLINK_INTERVAL_s			= 1			# 死活判別用のLED点滅サイクル

# チャタリング防止（ms単位）
PUSH_GLITCH_TIME			=  1 * 1000 #  1秒（チャタリング防止）

# ボタン状況
PUSH_NONE				= 0	# 何もしてない
PUSH_PRESSING			= 1 # 押し続けている
PUSH_1CLICK				= 2 # 1クリック（警報停止、音声時計など）
PUSH_LONGPRESS			= 3 # ロングプレス（モード切替）
PUSH_SUPER_LONGPRESS	= 4
PUSH_ULTRA_LONGPRESS	= 5 # 超ロングプレス（電源断）

# --------------------- ディスプレイ関係 ---------------------
# スクリーンセーバー
SCREEN_SAVER_TIMER_m	= 5	# スクリーンセーバータイム（分）

# バックライト制御用（setBackLightで使用）
EPD_BACKLIGHT_SW_MAIN 	= 0
EPD_BACKLIGHT_SW_SAVER 	= 1

# --------------------- デバイスのオブジェクト ---------------------

# pigpioデバイス for GPIO
import pigpio
pi = pigpio.pi()

#SPI (WaveshareのLCD)
import spidev
spi = spidev.SpiDev()
spi.open(0, 1) # bus0, cs1
spi.max_speed_hz = 1000000

# --------------------- TFTディスプレイ ---------------------
import LCD_1inch69
epd = LCD_1inch69.LCD_1inch69()
epd.Init()
epd.clear()

# 各画面領域のサイズt
# 1.画面全体
EPD_WIDTH	= 240 
EPD_HEIGHT	= 280

# 2.上部ステータスバー
SBAR_HEIGHT = 20 # ステータスバーの高さ。これで画面を上下分割している
SBAR_WIDTH	= EPD_WIDTH

# 3.メイン描画エリア
MAIN_HEIGHT	= EPD_HEIGHT - SBAR_HEIGHT
MAIN_WIDTH	= EPD_WIDTH

# --------------------- 各画面でのfont ---------------------
info_title_font		= ImageFont.truetype( 'mplus-1mn-bold.ttf', 14)
info_content_font	= ImageFont.truetype( 'mplus-1mn-regular.ttf', 14)

normalFont 			= ImageFont.truetype( 'Font.ttc', 16)
largeFont  			= ImageFont.truetype( 'mplus-1mn-light.ttf', 50)

digitalLargeFont	= ImageFont.truetype( 'segment-std.otf', 80 )
digitalPressFont	= ImageFont.truetype( 'segment-std.otf', 68 )
digitalMiddleFont	= ImageFont.truetype( 'segment-std.otf', 32 )
digitalSmallFont	= ImageFont.truetype( 'segment-std.otf', 18 )
unitFont			= ImageFont.truetype( 'Font.ttc', 18)

clockLargeFont		= ImageFont.truetype( 'segment-bold.ttf', 65 )
clockNormalFont 	= ImageFont.truetype( 'Font.ttc', 32)

menu_font  			= ImageFont.truetype( 'Font.ttc', 20)

# ------------------------------------------------------------------------------
# デバイス間通信

# デバイス間で依頼する際のキーワード（なんでもいいんだけど）
COMM_GET_WASHER_STATUS	= "get_washer_status"	# 食洗器の状態確認
COMM_BEGIN_RAIN_ALERT	= "begin_rain_alert"	# 雨降りはじめ警報
COMM_END_RAIN_ALERT		= "end_rain_alert"		# その終了


# ------------------------------------------------------------------------------

# 各モードの画面更新頻度（各モードで差をつけられるよう、最小間隔の倍数で更新する）
DISP_UPDATE_INTERVAL_s					= 10 # 画面更新の最小間隔（秒）
DISP_MODE_NORMAL_UPDATE_INTERVAL		= 30	/ DISP_UPDATE_INTERVAL_s
DISP_MODE_CLOCK_UPDATE_INTERVAL			= 10 	/ DISP_UPDATE_INTERVAL_s
DISP_MODE_USEFUL_UPDATE_INTERVAL		= 10 	/ DISP_UPDATE_INTERVAL_s
DISP_MODE_DEVICE_INFO_UPDATE_INTERVAL	= 10 	/ DISP_UPDATE_INTERVAL_s

# Line通知用 API TODO:LINEに代わるAPIを見つけないと・・・。
LINE_TOKEN = "IslzD4ysN3G73g7pYMCgpvRUU1vORlUeYbxAHZqoQgP"

# --------------------- 初期設定地 ---------------------
SHUTDOWN_TIMER  = 2

# ------------------------------------------------------------------------------
# RAIN関係の各種設定

TIMER_RAIN_BEGIN_ALERT			= 182	/TIMER_TICK # 雨が降る・やんだ際のアラーム継続時間
TIMER_RAIN_BEGIN_ALERT_SHORT	= 20	/TIMER_TICK # 夜の間のアラーム時間（短めにする）

TIMER_RAIN_STOP_ALERT			= 62	/TIMER_TICK # 雨が降る・やんだ際のアラーム継続時間
TIMER_RAIN_STOP_ALERT_SHORT		= 20	/TIMER_TICK # 夜の間のアラーム時間（短めにする）

TIMER_RAIN_MESSAGE				= 30		/TIMER_TICK # 雨が降ってきた！の繰り返しタイマ
TIMER_RAIN_MODE_CHATTERING		= 90*60 /TIMER_TICK # 雨⇔晴の間のチャタリング防止待ち時間

TIMER_RAINTIME					= 8	 # 長時間雨の閾値（時間）

# 天候モード
WEATHER_MODE_FINE	= 0
WEATHER_MODE_BEGIN	= 1
WEATHER_MODE_RAIN	= 2
WEATHER_MODE_STOP	= 3
weather_mode_label	= ["fine", "begin", "rain", "stop"]

# お休みモード
SLEEP_MODE_WAKEUP	= 0
SLEEP_MODE_SLEEP	= 1
sleep_mode_label	= ["wakeup", "sleep"]

# 時間帯による音声制御
TALK_FORCE			= 1	 # 時間帯によらず喋る
TALK_MORNING		= 2	 # 早朝から喋る
TALK_DAY			= 3	 # 昼間時間帯だけ

TIME_MIDNIGHT		=  0 # NIGHT MODE（音声オフ）の開始
TIME_SUNRISE		=  5 # 日の出
TIME_MORNING		=  6 # 早朝時刻
TIME_DAY			=  8 # 雨監視開始
TIME_NIGHT			= 22 # 就寝勧告始まり
TIME_SLEEP			= 23 # お休み開始

# 時刻の区分け（SUNRISE,MORNING,DAY,NIGHT,SLEEP,MIDNIGHT)
TIME_MODE_SUNRISE	= 0
TIME_MODE_MORNING	= 1
TIME_MODE_DAY		= 2
TIME_MODE_NIGHT		= 3
TIME_MODE_SLEEP		= 4
TIME_MODE_MIDNIGHT= 5
time_mode_label		= ["sunrise","morning","day","night","sleep","midnight"]

# ------------------------------------------------------------------------------
# 画面表示モード(さらりと書いてるけど、システム全体の動作を決めてます)
DISP_MODE_NORMAL		= 0
DISP_MODE_CLOCK			= 1
DISP_MODE_USEFUL		= 2
DISP_MODE_DEVICE_INFO	= 3

DISP_MODE_NAME	= ["NORMAL", "CLOCK", "USEFUL", "DEVICE"]
DISP_MODE_label	= ["NORMAL", "CLOCK", "USEFUL", "DEVICE"]

# ------------------------------------------------------------------------------
# ステータスバー

SBAR_APPLE_ICON			= Image.open( "icon/icon_apple7.jpg" )
SBAR_FINDER_ICON		= Image.open( "icon/icon_multifinder.jpg" )
SBAR_CHILD_NG_ICON	= Image.open( "icon/icon_dokuro.jpg" )

SBAR_WEATHER_ICON_FINE	= Image.open( "icon/icon_fine.jpg" )
SBAR_WEATHER_ICON_RAIN	= Image.open( "icon/icon_rain.jpg" )

SBAR_WEATHER_ICON_POS	= (EPD_WIDTH-43, 0)
SBAR_CLOCK_POS		= ( 90, -4)
SBAR_SOC_POS			= (160, -2)
SBAR_MOIST_POS		= (150, -4)
SBAR_APPLE_POS		= ( 35, 0)

DIALOG_WIDTH			= 200
DIALOG_HEIGHT			= 100
DIALOG_BEGIN_ICON		= Image.open("icon/dialog_begin3.bmp")

# ------------------------------------------------------------------------------
# メイン描画エリア

ICON_BYE_MAC			= Image.open( "icon/icon_bye.bmp" )
ICON_SAD_MAC			= Image.open( "icon/icon_sad.bmp" )

ICON_RAIN					= Image.open( "icon/icon_rain.png")

# ------------------------------------------------------------------------------
# 汎用ダイアログ関係

DIALOG_POS		= (50, 30)
DIALOG_TIMER	= 30	# １回あたりのダイアログ表示秒

# ------------------------------------------------------------------------------
# MODE1（ノーマル表示）関係
MODE_NORMAL_MOIST_POS = (40, 150)

# ------------------------------------------------------------------------------h
# MODE2（時計表示）関係
MODE_CLOCK_CLOCK_POS			= (10 , 85)
MODE_CLOCK_DATE_POS			= (150,160)

# ------------------------------------------------------------------------------
# MODE3（便利表示）関係

MODE_USEFUL_MOIST_POS		= (5, 30)
MODE_USEFUL_MOIST_UNIT_POS	= ( 70, 100)

MODE_USEFUL_HUM_POS			= (5,  155)
MODE_USEFUL_HUM_UNIT_POS	= (70, 222)

MODE_USEFUL_TEMP_POS		= (120, 30)
MODE_USEFUL_TEMP_UNIT_POS	= (210, 100)

MODE_USEFUL_PRESS_POS		= (85 , 157)
MODE_USEFUL_PRESS_UNIT_POS	= (200, 217)

# ------------------------------------------------------------------------------
# MODE4（デバイス表示）関係



# ------------------------------------------------------------------------------
# ここから先は実行コード

# プルアップ・ダウンの設定が面倒なので少しだけ省力化
def set_pull_up_down( pin, updown ):
	pi.set_mode( pin, pigpio.INPUT )
	pi.set_pull_up_down( pin, updown )

# 出力ピンも少しだけ省力化
def set_mode( pin, highlow ):
	pi.set_mode( pin, pigpio.OUTPUT )
	pi.write( pin, highlow )

# 複数のピンに同じ出力をやる
def gpio_write( out, *pins ):
	for pin in pins:
		pi.write( pin, out )


# 各デバイスやGPIOの初期化
# 各種出力ピン（LED、CO2、EPD制御）
#set_mode( FRONT_LED_PIN, pigpio.HIGH )

# 各種入力ピン（SW、リセット）
set_pull_up_down( SLIDE_SW_PIN, pigpio.PUD_UP )
set_pull_up_down( FRONT_BTN_PIN, pigpio.PUD_UP )

# CDS（明暗）
set_pull_up_down( CDS_PIN, pigpio.PUD_UP )
set_pull_up_down( PIR_PIN, pigpio.PUD_DOWN )
