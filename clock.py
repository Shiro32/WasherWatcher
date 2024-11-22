#!usr/bin/env python
# -*- coding: utf-8 -*-

#　2024/11/21 最初

from cfg import *   # 定数関係
import globals as g # グローバル変数・関数
import datetime

# --------------------- clockモジュール内のglobal ---------------------

def draw_clock():
	dt = datetime.datetime.now()

	g.draw_main.text( MODE_CLOCK_CLOCK_POS, dt.strftime("%H"), font=clockLargeFont, fill="black" )
	g.draw_main.text( MODE_CLOCK_CLOCK_POS, dt.strftime("%H:%M"), font=clockLargeFont, fill="black" )
	g.draw_main.text( MODE_CLOCK_DATE_POS, dt.strftime("%m/%d %a"), font=clockNormalFont, fill="black" )

