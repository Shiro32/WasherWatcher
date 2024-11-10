#!usr/bin/env python
# -*- coding: utf-8 -*-

# Flower-IoT用の定数・グローバル変数・サブルーチン集
# 読み込み先のpyファイルでは、from cfg import *　で全部読み込む
#
# 〇定数（SW_PINなど）
# 〇デバイスオブジェクト（pi, epd, bmeなど）
# 〇サブルーチン
# ×編集可能なglobal変数はここに書かない→globals.pyへ


# 変数定義のために先に読み込む
from PIL import Image,ImageDraw,ImageFont
import ambient

# --------------------- GPIOピン Setup ---------------------
FRONT_BTN_PIN	= 12	# いろいろ使うメインボタン
SOUND_SW_PIN	= 23	# 左：サウンドオフスイッチ
SAVER_SW_PIN	= 24	# 中：今のところ使い道無し
FRONT_LED_PIN	= 19	# 前面のLED

# 雨降り検出関係
RAIN_PIN		= 17		# Tweliteの雨情報のGPIO(in)
CDS_PIN			= 26		# 明暗検出CDSのGPIOピン(in)（もともと9だったけど入れ替え）

BME280_ADDR		= 0x76	# 環境センサ
ATP3012_ADDR	= 0x2e	# 音声合成IC
I2C_CH			= 1

TIMER_TICK			= 0.05	# タイムの最小単位。メインループのsleep値なので微妙

LED_OFF					= 0
LED_ON					= 1
LED_BLINK_SHORT = 2
LED_BLINK_LONG	= 3


# --------------------- 土壌水分関係 ---------------------
MOIST_THRESHOLD_DRY	= 40	# 土壌センサの「乾燥」判定
MOIST_THRESHOLD_WET	= 70 	# 土壌センサの「ずぶぬれ」判定
MOIST_DRY_MARGIN			= 3	# 乾燥側の復帰マージン
MOIST_WET_MARGIN			= 1	# 過湿潤側の復帰マージン

INTERVAL_MOIST_ALARM	= 120  # 何秒ごとに警報鳴らすか (120)
INTERVAL_MOIST_ALARM2	= 1800 # 乾燥・湿潤が完全に始まった後の警報間隔 (1800)
TIMER_MOIST_ALARM			= 600  # PRE状態のタイムアウト(600)

# --------------------- フロントボタン関係のタイマ ---------------------
# 各種タイマ（マイクロセカンド単位）
#PUSH_CHATTERING_TIME					= 0.1 * 1000000	# 0.2秒
PUSH_LONGPRESS_TIME_ms				= 1  * 1000 # 1秒
PUSH_SUPER_LONGPRESS_TIME_ms	= 6  * 1000 # 10秒（これだけmsなので注意）
#PUSH_ULTRA_LONGPRESS_TIME_ms	= 10 * 1000

LED_BLINK_INTERVAL_s	= 1

# チャタリング防止（ms単位）
PUSH_GLITCH_TIME			=  1 * 1000 #  1秒（チャタリング防止）

# ボタン状況
PUSH_NONE							= 0	# 何もしてない
PUSH_PRESSING					= 1 # 押し続けている
PUSH_1CLICK						= 2 # 1クリック（警報停止、音声時計など）
PUSH_LONGPRESS				= 3 # ロングプレス（モード切替）
PUSH_SUPER_LONGPRESS	= 4
PUSH_ULTRA_LONGPRESS	= 5 # 超ロングプレス（電源断）

# --------------------- ディスプレイ関係 ---------------------
# スクリーンセーバー
SCREEN_SAVER_TIMER_m		= 5	# スクリーンセーバータイム（分）

# バックライト制御用（setBackLightで使用）
EPD_BACKLIGHT_SW_MAIN 	= 0
EPD_BACKLIGHT_SW_SAVER 	= 1

# --------------------- デバイスのオブジェクト ---------------------

# pigpioデバイス for GPIO
import pigpio
pi = pigpio.pi()

# BME280センサー
import bme280
bme = bme280.bme280( pi, I2C_CH, BME280_ADDR )
bme.setup()

#SPI（ADCで使う）
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
EPD_WIDTH		= 240 
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

normalFont 				= ImageFont.truetype( 'Font.ttc', 16)
largeFont  				= ImageFont.truetype( 'mplus-1mn-light.ttf', 50)

digitalLargeFont	= ImageFont.truetype( 'segment-std.otf', 80 )
digitalPressFont	= ImageFont.truetype( 'segment-std.otf', 68 )
digitalMiddleFont	= ImageFont.truetype( 'segment-std.otf', 32 )
digitalSmallFont	= ImageFont.truetype( 'segment-std.otf', 18 )
unitFont					= ImageFont.truetype( 'Font.ttc', 18)

clockLargeFont		= ImageFont.truetype( 'segment-bold.ttf', 65 )
clockNormalFont 	= ImageFont.truetype( 'Font.ttc', 32)

menu_font  				= ImageFont.truetype( 'Font.ttc', 20)

# --------------------- ログ設定 ---------------------
# グラフレンジ
GRAPH_RANGE_LENGTH_m	= 60*12 # 分
GRAPH_RANGE_TICKS	= ["12hr","8hr","4hr","now"]


# 記録
SENSING_INTERVAL_s		= 2	# センサー計測間隔(秒)
SENSING_AVERAGE_TIMES = 5	#	欠測対応用の移動平均を何回で計算するか（グラフ更新とは非同期でOK）

FILE_WRITE_INTERVAL_s = 60	# ファイル記録間隔（秒）★回数にすべき
IOT_SEND_INTERVAL_s		= 60*5	# IoTクラウド(Ambient)への送信間隔(s)


# 記録用リングバッファのサイズ
# 結局はグラフ表示にしか使わないので、dot by dotとなる要素以上に持っていても無駄
# RECORD_MAX			= 6*60*12 # どれだけ前のデータまで残すか（個数）
RECORD_MAX					= 200	# およそのグラフ幅（なるべくdot by dotでデータ作りたいため）
RECORD_INTERVAL_s = GRAPH_RANGE_LENGTH_m *60 / RECORD_MAX # 1目盛りあたりの間隔秒（これでストアする）

# 各モードの画面更新頻度（各モードで差をつけられるよう、最小間隔の倍数で更新する）
DISP_UPDATE_INTERVAL_s						= 10 # 画面更新の最小間隔（秒）
DISP_NORMAL_UPDATE_INTERVAL				= 30	/ DISP_UPDATE_INTERVAL_s
DISP_TREND_UPDATE_INTERVAL				= 300 / DISP_UPDATE_INTERVAL_s
SYSTEM_MODE4_UPDATE_INTERVAL				= 30 	/ DISP_UPDATE_INTERVAL_s
DISP_CLOCK_UPDATE_INTERVAL				= 10 	/ DISP_UPDATE_INTERVAL_s
DISP_DEVICE_INFO_UPDATE_INTERVAL	= 10 	/ DISP_UPDATE_INTERVAL_s


# Ambient API
AMBIENT_CHANNEL_ID	= "57270"
AMBIENT_WRITE_KEY	= "8c1bd84775d65bb5"

# Line通知用 API
LINE_TOKEN = "IslzD4ysN3G73g7pYMCgpvRUU1vORlUeYbxAHZqoQgP"

# --------------------- 初期設定地 ---------------------
SHUTDOWN_TIMER  = 2

# ------------------------------------------------------------------------------
# RAIN関係の各種設定

TIMER_RAIN_BEGIN_ALERT				= 182	/TIMER_TICK # 雨が降る・やんだ際のアラーム継続時間
TIMER_RAIN_BEGIN_ALERT_SHORT	= 20	/TIMER_TICK # 夜の間のアラーム時間（短めにする）

TIMER_RAIN_STOP_ALERT				= 62	/TIMER_TICK # 雨が降る・やんだ際のアラーム継続時間
TIMER_RAIN_STOP_ALERT_SHORT	= 20	/TIMER_TICK # 夜の間のアラーム時間（短めにする）

TIMER_RAIN_MESSAGE					= 30		/TIMER_TICK # 雨が降ってきた！の繰り返しタイマ
TIMER_RAIN_MODE_CHATTERING	= 90*60 /TIMER_TICK # 雨⇔晴の間のチャタリング防止待ち時間

TIMER_RAINTIME		= 8	 # 長時間雨の閾値（時間）

# 天候モード
WEATHER_MODE_FINE		= 0
WEATHER_MODE_BEGIN	= 1
WEATHER_MODE_RAIN		= 2
WEATHER_MODE_STOP		= 3
weather_mode_label	= ["fine", "begin", "rain", "stop"]

# お休みモード
SLEEP_MODE_WAKEUP	= 0
SLEEP_MODE_SLEEP	= 1
sleep_mode_label	= ["wakeup", "sleep"]

# 時間帯による音声制御
TALK_FORCE				= 1	 # 時間帯によらず喋る
TALK_MORNING			= 2	 # 早朝から喋る
TALK_DAY					= 3	 # 昼間時間帯だけ

TIME_MIDNIGHT			=  0 # NIGHT MODE（音声オフ）の開始
TIME_SUNRISE			=  5 # 日の出
TIME_MORNING			=  6 # 早朝時刻
TIME_DAY					=  8 # 雨監視開始
TIME_NIGHT				= 22 # 就寝勧告始まり
TIME_SLEEP				= 23 # お休み開始

# 時刻の区分け（SUNRISE,MORNING,DAY,NIGHT,SLEEP,MIDNIGHT)
TIME_MODE_SUNRISE	= 0
TIME_MODE_MORNING	= 1
TIME_MODE_DAY			= 2
TIME_MODE_NIGHT		= 3
TIME_MODE_SLEEP		= 4
TIME_MODE_MIDNIGHT= 5
time_mode_label		= ["sunrise","morning","day","night","sleep","midnight"]

# ------------------------------------------------------------------------------
# 画面表示モード(さらりと書いてるけど、システム全体の動作を決めてます)
SYSTEM_MODE_NORMAL	= 0
SYSTEM_MODE_TREND		= 1
SYSTEM_MODE_MODE4		= 2
SYSTEM_MODE_CLOCK		= 3
SYSTEM_MODE_DEVICE_INFO= 4

SYSTEM_MODE_NAME = ["NORMAL", "TREND", "MODE4", "CLOCK", "DEVICE"]
system_mode_label = ["NORMAL", "TREND", "MODE4", "CLOCK", "DEVICE"]

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

DIALOG_POS = (50, 30)
DIALOG_TIMER		= 30	# １回あたりのダイアログ表示秒


# ------------------------------------------------------------------------------
# MODE1（ノーマル表示）関係

# メインふじきゅんの変更タイマ
# MODE1のインターバル（30秒程度）×この回数で更新
FUJIKYUN_UPDATE_INTERVAL_t = 20


PIC_DRY1		= Image.open( "face/dry1.jpg" )
PIC_DRY2		= Image.open( "face/dry2.jpg" )
PIC_DRY3		= Image.open( "face/dry3.jpg" )
PIC_DRY4		= Image.open( "face/dry4.jpg" )
PICS_DRY = [
	PIC_DRY1, PIC_DRY2, PIC_DRY3, PIC_DRY4
]


PIC_NORMAL1 = Image.open( "face/normal1.jpg" )
PIC_NORMAL2 = Image.open( "face/normal2.jpg" )
PIC_NORMAL3 = Image.open( "face/normal3.jpg" )
PIC_NORMAL4 = Image.open( "face/normal4.jpg" )
PIC_NORMAL5 = Image.open( "face/normal5.jpg" )
PIC_NORMAL6 = Image.open( "face/normal6.jpg" )
PIC_NORMAL7 = Image.open( "face/normal7.jpg" )
PIC_NORMAL8 = Image.open( "face/normal8.jpg" )
PIC_NORMAL9 = Image.open( "face/normal9.jpg" )
PIC_NORMAL10 = Image.open( "face/normal10.jpg" )
PIC_NORMAL11 = Image.open( "face/normal11.jpg" )
PIC_NORMAL12 = Image.open( "face/normal12.jpg" )
PICS_NORMAL = [
	PIC_NORMAL1, PIC_NORMAL2, PIC_NORMAL3, PIC_NORMAL4,
	PIC_NORMAL5, PIC_NORMAL6, PIC_NORMAL7, PIC_NORMAL8,
	PIC_NORMAL9, PIC_NORMAL10, PIC_NORMAL11, PIC_NORMAL12
]

PIC_WET1		= Image.open( "face/wet1.jpg" )
PIC_WET2		= Image.open( "face/wet2.jpg" )
PICS_WET = [
	PIC_WET1, PIC_WET2
]

PIC_RAIN		= Image.open( "face/rain.jpg" )


PIC_THANKS1	= Image.open( "face/thanks1.jpg" )
PIC_THANKS2	= Image.open( "face/thanks2.jpg" )
PIC_THANKS3	= Image.open( "face/thanks3.jpg" )
PICS_THANKS = [
	PIC_THANKS1, PIC_THANKS2, PIC_THANKS3
]

MODE_NORMAL_MOIST_POS = (40, 150)

# ------------------------------------------------------------------------------h
# MODE2（トレンドグラフ表示）関係

MOIST_CURRENT_POS 	= (40,60)
TEMP_CURRENT_POS		= (40,85)
HUM_CURRENT_POS 		= (40,100)
PRESS_CURRENT_POS		= (40,115)

# グラフY軸の最大値・最小値
TEMP_MIN				= 15
TEMP_MAX				= 35
MOIST_MIN				= 30
MOIST_MAX				= 80

# ------------------------------------------------------------------------------
# MODE3（４分割）関係

MODE2_MOIST_POS				= (5, 30)
MODE2_MOIST_UNIT_POS	= ( 70, 100)

MODE2_HUM_POS					= (5,  155)
MODE2_HUM_UNIT_POS		= (70, 222)

MODE2_TEMP_POS				= (120, 30)
MODE2_TEMP_UNIT_POS		= (210, 100)

MODE2_PRESS_POS				= (85 , 157)
MODE2_PRESS_UNIT_POS	= (200, 217)

# ------------------------------------------------------------------------------
# MODE4（時計）関係
MODE4_CLOCK_POS			= (10 , 85)
MODE4_DATE_POS			= (150,160)

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
set_mode( FRONT_LED_PIN, pigpio.HIGH )

# 各種入力ピン（SW、リセット）
set_pull_up_down( SOUND_SW_PIN, pigpio.PUD_UP )
set_pull_up_down( SAVER_SW_PIN, pigpio.PUD_UP )
set_pull_up_down( FRONT_BTN_PIN, pigpio.PUD_UP )


# Twelite（雨検出）、CDS（明暗）
set_pull_up_down( RAIN_PIN, pigpio.PUD_UP )
set_pull_up_down( CDS_PIN, pigpio.PUD_UP )

# --------------------- Ambientのインスタンス ---------------------
amb = ambient.Ambient(AMBIENT_CHANNEL_ID, AMBIENT_WRITE_KEY)

