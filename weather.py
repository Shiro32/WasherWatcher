#!usr/bin/env python
# -*- coding: utf-8 -*-

# 天気予報読み上げのモジュール
# もともと、〇〇太郎シリーズで使っていたものを、そのままWasherに移植
#
# TweliteのGPIOはそのままSocket通信で代用する
#
# 1.BeautifulSoupで適当なサイトから天気予報を拾ってくる
# 2.pykakasiでローマ字変換
# 3.ATP3012で喋らせる
#
# 2024/11/26 Flower IoTから移植

from pykakasi import kakasi
import requests
import re
import unicodedata
from bs4 import BeautifulSoup
from cfg import *
import globals as g
import datetime
import weather_icon
from random import randrange as rnd

voices_atui2 = [
	"madama'da atu'ihiga tuzukimasune.",
	"atu'inode kiotuketekudasai."
	"ha'yaku suzu'siku/na'ruto i'idesune."]


APPID = "dj00aiZpPURQYWhZNkxsWlRwTSZzPWNvbnN1bWVyc2VjcmV0Jng9ZGU-"
POS   = "139.472086,35.359172"

# OpenWeather API
OW_API_KEY = 'ee2fa16463c7d123817fb43a5be6c65d'
OW_LATITUDE = '35.359172'
OW_LONGITUDE = '139.472086'
OW_UNITS = 'metric'
OW_BASE_URL = 'https://api.openweathermap.org/data/2.5/weather?'
OW_URL = OW_BASE_URL + 'lat=' + OW_LATITUDE + '&lon=' + OW_LONGITUDE + '&units=' + OW_UNITS + '&appid=' + OW_API_KEY

# Livedoor
LD_WEATHER_ID = "140010"
LD_WEATHER_URL = 'https://weather.tsukumijima.net/api/forecast/city/' + LD_WEATHER_ID

# かかし（漢字ローマ字変換）エンジンのインスタンス
kks = kakasi()

DICT_BEFORE = {'は、':'wa,','？':'?','！':'\'.','～':'kara',
	'（':',','）':',','「':',','」':',',', ':',','':'','. ':'.','．':'.',
	'湿った':'simetta'}
DICT_AFTER = {'uu':'u-','ou':'o-','ee':'e-','aa':'a-','ii':'i-','iu':'yu-','ha,':'wa,'}
DICT_COMMA = {'、':' ', '。':'. '}


# 雷雨接近中フラグ（予報が始まるとTrueになり、初回だけアラーム発信させるため）
approaching_rain = False

forecast_cache = [
	["明日","天気","ファイル",0,0,0],
	["明後日","天気","ファイル",0,0,0]
]



# ------------------------------------------------------------------------------
def check_rain_rader()->None:
	"""Yahooの雨雲レーダーをチェックして警報を出す
	定期的にscheduleで呼び出されて、チェックを入れる（！）
	パラメータも戻り値もなく、雨が降りそうなら音声警報を出すだけ
	"""
	global approaching_rain

	# Yahoo天気予報APIのURLを作り出す
	d = F"{datetime.datetime.now():%Y%m%d%H%M}"
	url = F'https://map.yahooapis.jp/weather/V1/place?appid={APPID}&coordinates={POS}&output=json&date={d}'
	g.log( "rader", F"URL:{url}" )

	# Yahooの天気予報APIから盗んでくるが、微妙に形状が違うときがあるのか、連想配列でエラーになることがある
	# しょうがないので、とりあえずtry-exceptでカバー
	try:
		# 実際にネットから拾う。WiFiが無ければexception
		response = requests.get(url)
		data = response.json()

		# rainsに今後の10分ごとの予報降水量を格納している（と思う）
		rains = data['Feature'][0]['Property']['WeatherList']['Weather']
		rains = [float(d.get("Rainfall")) for d in rains]

	except Exception as e:
		approaching_rain = False
		g.log( "rader", str(e) )
		return	# 後続がelse節なので不要ではある。finally節がある場合はそれが実行される！（）

	else:
		g.log( "rader", data )
		print( rains )

		# すでに現在雨が降っているなら、さっさと終了する
		if( rains[0]>0 ):
			approaching_rain = True
			return

		# 1時間先までの降雨状況をチェック
		i = 10
		for rain in rains[1:]:
			g.log("rader", F"{i:2}min = {rain}")
			if( rain>0 ): 
				# 音声は何回喋っても問題ないのでapproaching_rainのcheckは行わない
				g.talk(F"<NUMK VAL={i} COUNTER=funn>goni a'mega furi'hajime/so'u de'su.", TALK_DAY)

				# LINEはうっとうしいので、一連の注意報対応が終わるまで１回だけにする
				if( approaching_rain==False ):
					g.line_notify(F"花太郎：{i}分後に雨が降ってきそうですよ！") # LINE通知
				approaching_rain = True

				# 本当はここで雨警報のダイアログか何かを出したいのだけど、その仕組みが無い
				return
			i+=10

		# 降らない場合（１時間先まで降水量が０）
		approaching_rain = False
		return


# ------------------------------------------------------------------------------
def kanji2voice(message):
	g.log( "kanji", "[原文]\n"+message )

	# １行ずつ処理していく方式に変更。遅いカモ・・・。
	line=1
	for msg in message.split("\n"):
		for target, dest in DICT_BEFORE.items()	: msg = msg.replace(target,dest)
		msg = kks.convert(msg)
		msg = "".join( [d.get("hepburn") for d in msg])
		for target, dest in DICT_AFTER.items()	: msg = msg.replace(target,dest)
		for target, dest in DICT_COMMA.items()	: msg = msg.replace(target,dest)

		msg = unicodedata.normalize('NFKC',msg)
		msg = re.sub("([0-9]+)", "<NUMK VAL=\\1>", msg)
		msg = re.sub("\.", "", msg )

		g.log( "kanji", F"[{line:02}] : {msg}" )
		g.talk( msg, TALK_FORCE )
		line+=1

# ------------------------------------------------------------------------------
def update_forecast_weather():
	"""
	Livedoor天気予報にアクセスして天気情報を更新する
	・多頻度で呼ばれるとしんどいので、shceduleから数時間おきに呼ばれる
	・常時はcacheを返す
	・結果は、forecast_cacheリストに格納
	
	"""
	global forecast_cache

	try:
		# LiveDoor天気を取得（yahooでもいいような・・・）
		ld_response = requests.get(LD_WEATHER_URL)
		ld_weather = ld_response.json()

	except Exception as e:
		g.log( "WEATHER", "ネット接続なし")
		return False

	else:
		# 翌日の天気予報
		tomorrow_telop = ld_weather['forecasts'][1]['telop']
		tomorrow_dt = datetime.datetime.strptime(ld_weather['forecasts'][1]['date'], '%Y-%m-%d').date()
		tomorrow_date = tomorrow_dt.strftime('%m月%d日')
		tomorow_image = "weather_icon/"+weather_icon.half_icon[tomorrow_telop]
		am_rain = ld_weather['forecasts'][1]['chanceOfRain']['T06_12'][:-1]
		pm_rain = ld_weather['forecasts'][1]['chanceOfRain']['T12_18'][:-1]
		max_temp = ld_weather['forecasts'][1]['temperature']['max']['celsius']
		min_temp = ld_weather['forecasts'][1]['temperature']['min']['celsius']
		day_rain = max(am_rain, pm_rain)
		forecast_cache[1]=tomorrow_date, tomorrow_telop, tomorow_image, day_rain, max_temp, min_temp

		# 今日の天気予報
		tomorrow_telop = ld_weather['forecasts'][0]['telop']
		tomorrow_dt = datetime.datetime.strptime(ld_weather['forecasts'][0]['date'], '%Y-%m-%d').date()
		tomorrow_date = tomorrow_dt.strftime('%m月%d日')
		tomorow_image = "weather_icon/"+weather_icon.half_icon[tomorrow_telop]
		am_rain = ld_weather['forecasts'][0]['chanceOfRain']['T06_12'][:-1]
		pm_rain = ld_weather['forecasts'][0]['chanceOfRain']['T12_18'][:-1]
		max_temp = ld_weather['forecasts'][0]['temperature']['max']['celsius']
		min_temp = ld_weather['forecasts'][0]['temperature']['min']['celsius']
		day_rain = max(am_rain, pm_rain)
		forecast_cache[0]=tomorrow_date, tomorrow_telop, tomorow_image, day_rain, max_temp, min_temp

def get_forecast_weather( days: int ):
	return forecast_cache[days]

def get_forecast_temp_rain( days:int ):
	try:
		res = requests.get("https://weather.yahoo.co.jp/weather/jp/14/4610.html")
		soup = BeautifulSoup(res.text, "html.parser")
		if( days==0 ):		# 今日の天気
			temp_max 	= soup.select("#main div.forecastCity table tr td:nth-child(1) div ul li.high em")[0].contents[0]
			temp_min 	= soup.select("#main div.forecastCity table tr td:nth-child(1) div ul li.low em")[0].contents[0]
			rain_AM 	= soup.select("#main div.forecastCity table tr td:nth-child(1) div table tr.precip td:nth-child(3)")[0].contents[0]
			rain_PM 	= soup.select("#main div.forecastCity table tr td:nth-child(1) div table tr.precip td:nth-child(4)")[0].contents[0]
		elif( days==1 ):	# 明日の天気
			temp_max 	= soup.select("#main div.forecastCity table tr td:nth-child(2) div ul li.high em")[0].contents[0]
			temp_min 	= soup.select("#main div.forecastCity table tr td:nth-child(2) div ul li.low em")[0].contents[0]
			rain_AM 	= soup.select("#main div.forecastCity table tr td:nth-child(2) div table tr.precip td:nth-child(3)")[0].contents[0]
			rain_PM 	= soup.select("#main div.forecastCity table tr td:nth-child(2) div table tr.precip td:nth-child(4)")[0].contents[0]
		
		return temp_min, temp_max, rain_AM, rain_PM
	
	except Exception as e:
		g.log( "WEATHER", f"ネット接続なし:{e}" )
		return False, False, False, False

# ------------------------------------------------------------------------------
def check_weather_info( days:int, voice:int )->None:
	"""	ヤフーニュースのトップページ情報を取得して喋る
	メインルーチン（flowerやrainから呼ばれる）
	days: 0→今日の天気、1→明日の天気
	voice: アナウンスの冒頭。0→「きょうの」, 1→「あしたの」
	"""
	
	g.log( "weather", "forecasting..." )
	err = False

	# 天気予報を拾ってくるので、エラーに備えてtry-exeption

	g.talk( ("kyo'u" if voice==0 else "ashi'ta")+"no te'nkiwo osirasesimasu.", TALK_FORCE)

	# 気温＆降水確率
	# 当初は気象庁APIだったけど面倒くさくなったので、Yahoo天気予報をスクレイピング
	temp_min, temp_max, rain_AM, rain_PM = get_forecast_temp_rain( days )

	if temp_min==False:
		g.log( "weather", "errorダス" )
		g.talk("te'nki yo'houni tunagarimasen.", TALK_FORCE)

	else:
		# 降水確率
		if( rain_AM!="---" ):	# 過ぎた時刻の場合は"---"となるためスキップ
			rain_AM = int( str(rain_AM)[:-1] )
			g.talk( "goze'nchuuno kou'suikakurituwa <NUMK VAL="+str(rain_AM)+" counter=pa-se'nto>.", TALK_FORCE )
		else:
			rain_AM = 0

		if( rain_PM!="---" ):
			rain_PM = int( str(rain_PM)[:-1] )

			# 午前・午後で降水確率が同じ場合の「も」の処理を入れている
			mo = "mo" if rain_AM==rain_PM else "wa"
			g.talk( "go'go" + mo + " <NUMK VAL="+str(rain_PM)+" counter=pa-se'nto> de'su.", TALK_FORCE )
		else:
			rain_PM = 0

		if  ( rain_AM>=80 or rain_PM>=80 ) : g.talk( "kaku'jituni furima'sune.", TALK_FORCE )
		elif( rain_AM>=50 or rain_PM>=50 ) : g.talk( "nen'notame ka'sawo motteittahouga yosa'soudesune.", TALK_FORCE )
		elif( rain_AM>=30 or rain_PM>=30 ) : g.talk( "mo'sikasuruto fu'rukamosiremasenne.", TALK_FORCE )

		# 気温情報
		temp_max = int(str(temp_max))
		temp_min = int(str(temp_min))
		g.talk( "yosou'/saiko'ukionwa <NUMK VAL="+str(temp_max)+" counter=do'> de'su.", TALK_FORCE)
	#		g.talk( "yosou'/saite'ikionwa <NUMK VAL="+str(temp_min)+" counter=do'> de'su.", TALK_FORCE)		

		if(   temp_max>35 ) : g.talk( "mo-retuni atu'soudesune.", TALK_FORCE )
		elif( temp_max>30 ) : g.talk( voices_atui2[rnd(len(voices_atui2))], TALK_FORCE )
		elif( temp_max>25 ) : g.talk( "suko'si sugo'siyasuku narima'sitane.", TALK_FORCE )
		else				: g.talk( "ma'a futu'u de'su.", TALK_FORCE )

