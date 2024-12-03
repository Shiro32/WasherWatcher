#!/usr/bin/python
# -*- coding:utf-8 -*-
import sys
import os


import time
import requests
import json
import math
from datetime import datetime, timedelta, date

API_KEY = "ee2fa16463c7d123817fb43a5be6c65d"
LATITUDE = "139.472086"
LONGITUDE = "35.359172"
TSUKURUMIJIMA_TENKI_CODE = "140010"
UNITS = 'metric'

BASE_URL = 'https://api.openweathermap.org/data/2.5/weather?'
URL = BASE_URL + 'lat=' + LATITUDE + '&lon=' + LONGITUDE + '&units=' + UNITS + '&appid=' + API_KEY

TSUKURUMIJIMA_TENKI_URL = 'https://weather.tsukumijima.net/api/forecast/city/' + TSUKURUMIJIMA_TENKI_CODE

black = 'rgb(0,0,0)'
white = 'rgb(255,255,255)'
grey = 'rgb(235,235,235)'



def write_to_screen():

    # openweathermap API
    response = requests.get(URL)
    data = response.json()
    
    print(data)
    
    # 天気予報 API（livedoor 天気互換）
    tsukumijima_response = requests.get(TSUKURUMIJIMA_TENKI_URL)
    tsukumijima = tsukumijima_response.json()

    # 気温・最高・最低を小数点第一まで表示する
    wather = str(tsukumijima['forecasts'][0]['detail']['weather']).replace('　', '')
    temp = '{:.1f}'.format(data['main']['temp'])
    temp_max = '{:.1f}'.format(data['main']['temp_max'])
    temp_min = '{:.1f}'.format(data['main']['temp_min'])

    DIFF_JST_FROM_UTC = 9
    now = datetime.utcnow() + timedelta(hours=DIFF_JST_FROM_UTC)
    w_list = ['（月）', '（火）', '（水）', '（木）', '（金）', '（土）', '（日）']
    today = now.today().weekday()
    time_str = now.strftime('%Y年%m月%d日' + w_list[today])


    # === 気温 ===
    print(f"{temp=}")
    print(f"{temp_max=}/{temp_min=}")


    # === アイコン + 日付 ===
    print( f"天気{data['weather'][0]['icon'] + '.png'}")
    print( f"{time_str=}/{wather=}")
    # === アイコン + 日付 ===

    # === 降水確率 ===
    print("降水確率")
    print(f"00-06:{tsukumijima['forecasts'][0]['chanceOfRain']['T00_06']}")
    print(f"06-12:{tsukumijima['forecasts'][0]['chanceOfRain']['T06_12']}")
    print(f"12-18:{tsukumijima['forecasts'][0]['chanceOfRain']['T12_18']}")
    print(f"18-24:{tsukumijima['forecasts'][0]['chanceOfRain']['T18_24']}")
        # === 降水確率 ===

    ## === 明日の天気 ===
    #tommorow_telop = tsukumijima['forecasts'][1]['telop']
    #tommorow_datetime = datetime.strptime(tsukumijima['forecasts'][1]['date'], '%Y-%m-%d').date()
    #tommorow_week = datetime.strptime(tsukumijima['forecasts'][1]['date'], '%Y-%m-%d').date().weekday()
    #tommorow = tommorow_datetime.strftime('%m月%d日' + w_list[tommorow_week])
    #icon_tomorow_image = Image.open(os.path.join(picdir, icon_mapping.half_icon[tommorow_telop]))
    #Himage.paste(icon_tomorow_image, (335, 335))
    #draw.text((320, 316), tommorow, font=font18, fill=0)
    #draw.text((325, 410), tommorow_telop, font=font16, fill=0)
    #draw.text((325, 430), '最高：' + tsukumijima['forecasts'][1]['temperature']['max']['celsius'] + '°C', font=font16, fill=0)
    #draw.text((325, 450), '最低：' + tsukumijima['forecasts'][1]['temperature']['min']['celsius'] + '°C', font=font16, fill=0)
    ## === 明日の天気 ===

    ## === 明後日の天気 ===
    #day_after_tomorrow_telop = tsukumijima['forecasts'][2]['telop']
    #day_after_tomorrow_datetime = datetime.strptime(tsukumijima['forecasts'][2]['date'], '%Y-%m-%d').date()
    #day_after_tomorrow_week = datetime.strptime(tsukumijima['forecasts'][2]['date'], '%Y-%m-%d').date().weekday()
    #day_after_tomorrow = day_after_tomorrow_datetime.strftime('%m月%d日' + w_list[day_after_tomorrow_week])
    #icon_tomorow_image = Image.open(os.path.join(picdir, icon_mapping.half_icon[day_after_tomorrow_telop]))
    #Himage.paste(icon_tomorow_image, (475, 335))
    #draw.text((460, 316), day_after_tomorrow, font=font18, fill=0)
    #draw.text((465, 410), day_after_tomorrow_telop, font=font16, fill=0)
    #draw.text((465, 430), '最高：' + tsukumijima['forecasts'][2]['temperature']['max']['celsius'] + '°C', font=font16, fill=0)
    #draw.text((465, 450), '最低：' + tsukumijima['forecasts'][2]['temperature']['min']['celsius'] + '°C', font=font16, fill=0)
    ## === 明後日の天気 ===

    ## === 更新の時間 ===
    #draw.text((627, 330), 'UPDATED', font=font35, fill=white)
    #current_time = datetime.now().strftime('%H:%M')
    #draw.text((627, 375), current_time, font=font60, fill=white)
    ## === 更新の時間 ===

    #epd.display(epd.getbuffer(Himage))


write_to_screen()
