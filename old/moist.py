#!usr/bin/env python
# -*- coding: utf-8 -*-

# 土壌水分処理のモジュール
# 2023/09/09 メインから分離

import random
import schedule
from random import randrange as rnd

from cfg import *   # 定数関係
import globals as g # グローバル変数・関数

voice_thank_you		= "omizu arigatou. ikikaerimashita."
voice_stop_alarm	= "suibu'nkeihouwo teisisi'masita."

voices_light_thirsty	= [
	"no'doga kawa'itekimashita",
	"suko'si no'doga/kawa'ite/kitanaaa",
	"no'doga/kawa'iterunen",
	"no'doga/kawa'itekitakamo/sirena'i/yo'una so'udemo/na'iyouna/ki'gasuru kyo'u ko'nogoro de'su"
]

voices_heavy_thirsty = [
	"no'doga do'ndon kawa'itekimashita.",
	"no'doga ge'kiretuni/kawa'iteimasu.",
	"ton'demonaku no'doga/kawa'iteimasu.",
	"mi  mi  mizuwo kuda'sai"
]

voice_light_wet = "cho'tto mizuga oosugidesu."
voices_heavy_wet = [
	"mizuga oosugidesu-",
	"mizuga oosugite i'kiga kurusiidesu-",
	"mizuga oosugite negusare sicha'isoudesu."
]

# --------------------- WET Voice setup ---------------------
# WET濃度に応じたアラート
# ・閾値は MOIST_THRESHOLD_DRY, _WETでこれを超えたら乾燥・湿潤開始モードに入る
# ・一定時間経過 or 前ボタン押下で、乾燥・湿潤継続モードに入る
# ・モード遷移による音声警告はここでやる
#
# 急遽の水やりに備えて、１秒ごとに呼び出される（このためだけに）
# 直前の状態から、上昇・下降・停滞を判定して音声警告
#
#  通常				：待機状態
#
#  通常→乾燥	：警報ダイアログ（乾燥）
#  乾燥→乾燥	：１時間ごとに警報ダイアログ、ステータスバー（乾燥）
#	 乾燥→通常	：感謝ダイアログ。復帰の不感帯は大きめ（給水前提）
#
#  通常→湿潤	：警報ダイアログ（過湿潤）　
#　湿潤→湿潤	：ステータスバー（過湿潤）だけ。ダイアログは出してもしょうがない
#  湿潤→通常	：警報復帰。自然乾燥しかないので不感帯は狭め。ダイアログ不要（あってもいいかも？）

# 土壌ステータス
MOIST_STATUS_DRY					= -2	# 渇き状態（１時間おきにDRYINGに戻す）
MOIST_STATUS_DRYING				= -1	# 渇きの始まり（アラート）
MOIST_STATUS_NORMAL				= 0		# 適切な状態
MOIST_STATUS_WETTING			= 1		# 過湿潤の始まり
MOIST_STATUS_WET 					= 2		# 過湿潤状態

moist_mode_label						= ["dry","drying","normal","wetting","wet"]

moist_status = MOIST_STATUS_NORMAL

# ------------------------------------------------------------------------------
def start_moist_status_wetting()->None:
	"""WETTINGの開始処理
	・過剰の警告ダイアログ（実際の表示はupdate_display側）
	・警告表示タイマのセット（インターバルで繰り返す）
	・WETへの自動遷移タイマのセット
	"""	
	global moist_status
	moist_status = MOIST_STATUS_WETTING

	g.update_display_immediately()	# いるの？
	alert_moist_wetting()
	schedule.every(INTERVAL_MOIST_ALARM).seconds\
		.do(alert_moist_wetting).tag("alert_moist_wetting")
	
	schedule.every(TIMER_MOIST_ALARM).seconds\
		.do(start_moist_status_wet).tag("start_moist_status_wet")

def alert_moist_wetting()->None:
	"""WETTING中の定期音声
	"""
	g.set_dialog( PIC_WET1, stop_alert_moist_wetting )
	g.talk( voice_light_wet,  TALK_DAY )

def stop_alert_moist_wetting()->None:
	"""ダイアログをボタンで消去した時の扱い
	"""
	g.talk( voice_stop_alarm, TALK_FORCE )
	start_moist_status_wet()

def start_moist_status_wet()->None:
	"""WETTINGを終えてWETへ
	"""
	global moist_status

	# WETTINGを終えるための後処理
	schedule.clear("start_moist_status_wet")		# WETTINGの自動遷移（WETTING→WET）
	schedule.clear("alert_moist_wetting")				# WETTINGの定期音声

	# WETの開始処理
	moist_status = MOIST_STATUS_WET
	g.update_display_immediately()
	schedule.every(INTERVAL_MOIST_ALARM2).seconds.do(alert_moist_wet).tag("alert_moist_wet")

def alert_moist_wet()->None:
	"""WET中の定期音声
	"""
	g.set_dialog( PICS_WET[rnd(len(PICS_WET))], stop_alert_moist_wet )
	g.talk( voices_heavy_wet[rnd(len(voices_heavy_wet))], TALK_DAY )

def stop_alert_moist_wet()->None:
	g.talk( "zubunure ara-mu ofudesu", TALK_FORCE )

# ------------------------------------------------------------------------------
def check_moist_wet()->None:
	"""湿潤状態が続いているかチェック
	実質的なWETのハンドラで、check_soil_moistで高頻度呼び出される
	通常に戻っているなら、各種タイマをキャンセルしてNormalに戻す
	"""
	global moist_status

	if g.newest_moist < MOIST_THRESHOLD_WET - MOIST_WET_MARGIN :
			g.log( "MOIST", "return to normal")	
			moist_status = MOIST_STATUS_NORMAL			# 土壌モードをNORMALに戻す

			# 各種定期実行をキャンセル（見つからない＝実行してない場合でも大丈夫）
			schedule.clear( "start_moist_status_wet" )	# WETTING→WETへの自動遷移
			schedule.clear( "alert_moist_wetting" )			# WETTINGでの定期音声
			schedule.clear( "alert_moist_wet" )					# WETでの定期音声
		
			# 感謝ダイアログ
			g.set_dialog( PICS_THANKS[rnd(len(PICS_THANKS))] )
			g.update_display_immediately()
			g.talk( "yatto zubu'nurejoutiwo dasshu'tu sima'sita.",  TALK_DAY )


# モード遷移のための補助関数（定期実行タイマのセットなど）
# 本来は各モードのハンドラだけでいいのだけど、モード遷移中の処理が必要で、
# そのための小さなハンドラが多数できてしまった・・・。
# ------------------------------------------------------------------------------
def start_moist_status_drying()->None:
	"""DRYINGの開始処理
	"""
	global moist_status
	moist_status = MOIST_STATUS_DRYING

	g.update_display_immediately()	# 必要なのか？
	alert_moist_drying()
	schedule.every(INTERVAL_MOIST_ALARM).seconds\
		.do(alert_moist_drying).tag("alert_moist_drying")

	schedule.every(TIMER_MOIST_ALARM)\
		.seconds.do(start_moist_status_dry).tag("start_moist_status_dry")

def alert_moist_drying()->None:
	"""DRYING中の定期音声
	"""
	g.set_dialog( PIC_DRY3, stop_alert_moist_drying )
	g.talk( voices_light_thirsty[rnd(len(voices_light_thirsty))],  TALK_DAY )

def stop_alert_moist_drying()->None:
	"""ダイアログをボタンで消去した時の扱い（しゃべるだけだけど・・・）
	"""
	g.talk( voice_stop_alarm, TALK_FORCE )
	start_moist_status_dry()

def start_moist_status_dry()->None:
	"""DRYINGを終えてDRYへ
	"""
	global moist_status

	# DRYINGを終えるための後処理
	schedule.clear("start_moist_status_dry")		# DRYINGの自動遷移（DRYING→DRY）
	schedule.clear("alert_moist_drying")				# DRYINGの定期音声

	# DRYの開始処理
	#・DRYでのタイマ設定（定期音声）
	moist_status = MOIST_STATUS_DRY
	g.update_display_immediately()
	schedule.every(INTERVAL_MOIST_ALARM2).seconds.do(alert_moist_dry).tag("alert_moist_dry")

def alert_moist_dry()->None:
	"""DRY中の定期音声
	"""
	g.set_dialog( PICS_DRY[rnd(len(PICS_DRY))], stop_alert_moist_dry )
	g.talk( voices_heavy_thirsty[rnd(len(voices_heavy_thirsty))], TALK_DAY )

def stop_alert_moist_dry()->None:
	g.talk( "nodo gekiretukawaki ara-mu ofudesu", TALK_FORCE )

# ------------------------------------------------------------------------------
def check_moist_dry()->None:
	"""乾燥状態が続いているかチェック
	実質的なDRYのハンドラで、check_soil_moistで高頻度呼び出される
	湿潤に戻っているなら、各種タイマをキャンセルしてNormalに戻す
	"""
	global moist_status

	if g.newest_moist > MOIST_THRESHOLD_DRY + MOIST_DRY_MARGIN:
			g.log( "MOIST", "return to normal")
			moist_status = MOIST_STATUS_NORMAL			# 土壌モードをNORMALに戻す

			# 各種定期実行をキャンセル（見つからない＝実行してない場合でも大丈夫）
			schedule.clear( "start_moist_status_dry" )	# DRYING→DRYへの自動遷移
			schedule.clear( "alert_moist_drying" )					# DRYINGでの定期音声
			schedule.clear( "alert_moist_dry" )							# DRYでの定期音声
		
			# 感謝ダイアログ
			g.set_dialog( PICS_THANKS[rnd(len(PICS_THANKS))] )
			g.update_display_immediately()
			g.talk( voice_thank_you, TALK_FORCE )

# ------------------------------------------------------------------------------
def check_soil_moist()->None:
	"""土壌水分量のチェック関数
	これがメインのチェック関数で、main関数から高頻度でコールされる
	これ１個で全土壌モードの処理をswich-case的にこなしているが、コードが長くなるので、
	サブルーチンに処理を丸投げしている→それをやめる
	"""
	global moist_status

	# moistレベルによる状態遷移をコード化
	# 1.通常状態の時
	if moist_status==MOIST_STATUS_NORMAL:			# 1.乾燥開始
		# 乾燥を検出
		if g.newest_moist < MOIST_THRESHOLD_DRY: start_moist_status_drying()
		# 過剰湿潤を検出
		if g.newest_moist > MOIST_THRESHOLD_WET: start_moist_status_wetting()

	# 2.乾燥開始、3.乾燥継続
	elif moist_status==MOIST_STATUS_DRYING or moist_status==MOIST_STATUS_DRY:	 check_moist_dry()

	# 4.過剰湿潤開始、5.過剰湿潤継続
	elif moist_status==MOIST_STATUS_WETTING or moist_status==MOIST_STATUS_WET: check_moist_wet()
		
# 改良前は300行
