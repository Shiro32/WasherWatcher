#!usr/bin/env python
# -*- coding: utf-8 -*-

#　2022/8/10
#　mac2.py：メイン処理＋CO2表示（トレンド、４モード）
#  news.py：ニュース処理
#  rain.py：twelite関係全部
#  cfg.py :定数・サブルーチン
#  globals.py: グローバル変数（フル修飾でアクセス）

from cfg import *   # 定数関係
import globals as g # グローバル変数・関数
import requests
from bs4 import BeautifulSoup
import re

# --------------------- newsモジュール内のglobal ---------------------
#news_titles = []
#news_contents = []
news_count = 1

news_titles = ["ニュース未取得"]
news_contents = ["ネットワーク未接続カモ・・・"]
news_index = 0

# ------------------------------------------------------------------------------
# Yahoo!からニュースを引っこ抜いてくる
# 数分おき（）にscheduleから呼ばれて、とりあえずバッファリング（実際に表示は別）


def update_news():
	global news_count, news_index
	global news_titles, news_contents

	# とりあえずバッファクリア
	del news_titles[0:], news_contents[0:]

	# ヤフーニュースのトップページ情報を取得する
	try:
		URL = "https://www.yahoo.co.jp/"
		res = requests.get(URL)

		# BeautifulSoupにヤフーニュースのページ内容を読み込ませる
		soup = BeautifulSoup(res.text, "html.parser")

		# URLに news.yahoo.co.jp/pickup が含まれるものを抽出する。
		data_list = soup.find_all(href=re.compile("news.yahoo.co.jp/pickup"))

		# ヤフーニュース見出のURL情報をループで取得し、リストで格納する。
		headline_link_list = [data.attrs["href"] for data in data_list]

		# ヤフーニュース見出のURLリストから記事URLを取得し、記事内容を取得する
		news_count = len(headline_link_list)
		news_index = 0

		for headline_link in headline_link_list:

			# ヤフーニュース見出のURLから、　要約ページの内容を取得する
			summary = requests.get(headline_link)

			# 取得した要約ページをBeautifulSoupで解析できるようにする
			summary_soup = BeautifulSoup(summary.text, "html.parser")

			# 本文タグを拾う
			c = summary_soup.find_all(class_=re.compile('highLightSearchTarget'))[0]

			t = re.match("(.*)"+NEWS_YAHOO_TITLE ,summary_soup.title.text )
			news_titles.append( t.group(1) )
			news_contents.append( c.text )
	except:
		news_titles.append("インターネット接続無し")
		news_contents.append("ネット接続が無いので、新規ニュースの獲得ができなくなってます（＞＜）")
		news_count = 1
		news_index = 0

# ------------------------------------------------------------------------------
# ニュースの表示
# update_displayから呼び出される
# 実際に画面更新を行うが、最後のepdへのフラッシュはupdate_displayでやる
# ★ニュースモードであっても、ステータスバーあたりにCO2を出しておくべきでは？
def display_news():
	global news_count, news_index

	g.log( "NEWS", "start" )

	news_title   = news_titles[news_index % news_count]
	news_content = news_contents[news_index % news_count]
	news_index += 1

	g.draw_main_black.text( (5,0), news_title, font=news_title_font )

	width, height = news_content_font.getsize("内容")

	# タプルはイミュータブルとのことで、ダサいけどY変数で・・・。
	# 多分画面をはみ出るけど無視して描画★止めた方がいい
	x, y = NEWS_CONTENT_POS
	x = 5
	news_lines = [news_content[i: i+NEWS_CONTENT_WIDTH] for i in range(0, len(news_content), NEWS_CONTENT_WIDTH)]
	for s in news_lines:
		g.draw_main_black.text( (x,y), s, font=news_content_font )
		y += height

	g.log( "NEWS", "end" )



