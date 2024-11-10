#!usr/bin/env python
# -*- coding: utf-8 -*-

#　2022/8/16
#　mac2.py：メイン処理＋CO2表示（トレンド、４モード）
#  news.py：ニュース処理
#  rain.py：twelite関係全部
#  clock.py:時計表示
#  cfg.py :定数・サブルーチン
#  globals.py: グローバル変数（フル修飾でアクセス）

from cfg import *   # 定数関係
import globals as g # グローバル変数・関数
import datetime

# --------------------- clockモジュール内のglobal ---------------------

def draw_clock():
	dt = datetime.datetime.now()

	g.draw_main.text( MODE4_CLOCK_POS, dt.strftime("%H"), font=clockLargeFont, fill="black" )
	g.draw_main.text( MODE4_CLOCK_POS, dt.strftime("%H:%M"), font=clockLargeFont, fill="black" )
	g.draw_main.text( MODE4_DATE_POS, dt.strftime("%m/%d %a"), font=clockNormalFont, fill="black" )

