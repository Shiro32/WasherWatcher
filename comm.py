#!usr/bin/env python
# -*- coding: utf-8 -*-

# WasherWatcherで用いる、デバイス間通信モジュール（socket通信）
#
# 1.子機からの雨情報。tweliteと同じ情報を送ってくる
#   rain_on ：twelite接点ON
# 	rain_off :twelite接点OFF 
#
# 2. 食洗器情報のやりとり。request-answer
#	〇子機→親機（request）
#	get_washer_status: 食洗器ステータス要求（子機→親機）
#	〇親機→子機（answer）
#	washer_empty	: 何も入っていない
#	washer_set		: タイマーセット済み
#	washer_unset	: 開閉検知したもののタイマーセットされていない（危険！）

import socket
import threading
import time
import cv2

from cfg import *
import globals as g

import washer

HOST = '0.0.0.0'
PORT = 65432

comm_status = "close"	# 通信回線を表す内部変数（socketで見れないのか？）

# --------------------- 子機とのSOCKET通信 ---------------------
# 子機から情報が来ると、commモジュールでこれらの値をセット
# メインモジュールでポーリングして各種処理のトリガーとする

comm_twelite_status = pigpio.HIGH	# 子機のtwelite（雨）の状態
comm_washer_request = False			# 子機からの食洗器状態リクエスト


def check_rain_status()->bool:
	return comm_twelite_status

def check_washer_request()->int:
	return comm_washer_request

# ------------------------------------------------------------------------------
def _receive_message_thread()->None:
	"""子機からのソケット通信を受信する
	・メインとは別スレッドで実行される（ほぼ受信待ちで待機）
	・受信情報に基づく処理はやり切れないので、各種グローバル変数に通知
	・メインスレッドがそれら変数をポーリングして処理開始
	"""

	global comm_status, comm_socket
	global comm_twelite_status, comm_washer_request

	# 通信が確保されている→受信待ちを続ける
	# 通信ができない→スレッド終了
	while True:
		try:
			# 相手からの受信待ち（ブロッキング）
			g.log("COMM RECV", "受信待ち開始")
			data = comm_socket.recv(1024)
			if not data:
				g.log("COMM RECV","相手から通信切断")
				break

			data = data.decode()
			g.log("COMM RECV", data )

			# 受信データによってさまざまな処理フラグを立てる
			if data==COMM_RAIN_LOW:
				comm_twelite_status = pigpio.LOW
			elif data==COMM_RAIN_HIGH:
				comm_twelite_status = pigpio.HIGH

			elif data==COMM_WASHER_REQUEST:
				comm_washer_request = True	# フラグセットなんだけど、そんなことしないで直接返信に変更
				send_message( COMM_WASHER_ANSWER+washer.washer_status() )
				#send_message( "OK" if washer.check_washer(call_from_child=True) else "NG" )

			elif data=="status":
				g.log("COMM", f"現状認識：{washer.washer_status()}")
				send_message( COMM_WASHER_ANSWER+washer.washer_status() )

			# 以下はデバッグ用
			elif data=="open":
				washer.washer_door = WASHER_DOOR_OPEN
				g.log("COMM", "「ドアOPEN」を受信")
			elif data=="close":
				washer.washer_door = WASHER_DOOR_CLOSE
				g.log("COMM", "「ドアCLOSE」を受信")
			elif data=="off":
				washer.washer_timer = WASHER_TIMER_OFF
				g.log("COMM", "「タイマーOFF」を受信")
			elif data=="2h":
				washer.washer_timer = WASHER_TIMER_2H
				g.log("COMM", "「タイマー2H」を受信")
			elif data=="4h":
				washer.washer_timer = WASHER_TIMER_4H
				g.log("COMM", "「タイマー4H」を受信")
			elif data=="empty":
				washer.washer_dishes = WASHER_DISHES_EMPTY
				g.log("COMM", "「EMPTY」を受信")
			elif data=="dirty":
				washer.washer_dishes = WASHER_DISHES_DIRTY
				g.log("COMM", "「DIRTY」を受信")
			elif data=="washed":
				washer.washer_dishes = WASHER_DISHES_WASHED
				g.log("COMM", "「WASHED」を受信")
			elif data=="save":
				washer.save_matching_flag = True
				g.log("COMM", "セーブしまっせ")
			elif data=="save2":
				washer.save_matching_flag2 = True
				g.log("COMM", "セーブしまっせ2")
			elif data=="shot":
				img = washer._capture_washer(False)
				cv2.imwrite("shot.png", img)
			elif data=="fullshot":
				img = washer._capture_washer(True)
				cv2.imwrite("shot-full.png", img)
			elif data=="check":
				washer.check_washer(call_from_child=False)
			elif data=="monitor":
				washer.monitor_washer()
			else:
				g.log("COMM RECV", f"知らないメッセージ:{data}")

			# 受信処理が終了し、またsocket.recvに戻って待機
		except ConnectionResetError:
			g.log("COMM RESV","相手によって接続がリセットされました。")
			break
		except Exception as e:
			g.log("COMM RESV", f"その他のエラーが発生しました: {e}")
			break

	# 通信をやめてスレッドを終了する
	comm_socket.close()
	comm_status = "close"

# ------------------------------------------------------------------------------
def _send_message_thread( msg:str ):
	"""子機にソケット通信で送信する
	・送信待ちでデッドロックしないように、メインとは別スレッドで実行
	・送信時に１回だけ起動し、送信できたら終了
	・ACK/NACKは何もせず、一方的に送信
	"""
	global comm_status, comm_socket
	g.log("COMM SEND", msg )

	try:
		if not comm_socket: # クライアントの接続が存在しない場合
			g.log("COMM SEND","flowerの接続がありません。")
		else:
			comm_socket.sendall(f"{msg}".encode())
			return

	except BrokenPipeError:
		g.log("COMM SEND", "flowerが接続を終了しました")

	except Exception as e:
		g.log("COMM SEND", f"メッセージ送信時にエラーが発生しました: {e}")
	
	# 通信をやめてスレッドを終了する
	comm_socket.close()
	comm_status = "close"

# ------------------------------------------------------------------------------
def _make_connection_thread():
	"""通信回線確立スレッド
	・子機との通信回線を維持するためのスレッド（メインとは別スレッド）
	・起動時に一度だけ呼ばれて、以降はずっと回線維持に務める
	・回線が確立（＝子機から接続）するまでブロックされ、接続出来たら受信スレッド立ち上げ
	"""
	global comm_status, comm_socket

	# 一度起動したら決して終了しないで、ずっと通信回線管理
	while True:
		if( comm_status=="close"):
			g.log("COMM CONNECT", "flowerと接続待ち...")
			comm_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

			comm_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			comm_socket.bind((HOST, PORT))	#バインディング
			comm_socket.listen()			#接続待ち

			comm_socket,adr= comm_socket.accept()	#接続されるまで、ここでブロッキング
			g.log("COMM CONNECT", "接続完了！")
			comm_status = "open"

			# 受信用スレッドを起動
			# （送信用スレッドは実際にメッセージ送信時に起動する）
			threading.Thread(target=_receive_message_thread, args=()).start() 

		# whileの最後（過剰なループ防止に２秒タイマ）
		time.sleep(2)

# ------------------------------------------------------------------------------
def send_message( msg:str )->None:
	"""子機にソケット通信で送信する
	・雨処理や食洗器処理のモジュールから呼ばれ、送信スレッドを作って終了
	・送信メッセージの意味解析や処理は何もしない
	
	msg: 送信文字列
	"""

	global comm_socket
	threading.Thread(target=_send_message_thread, args=(msg,)).start()

# ------------------------------------------------------------------------------
def init_comm()->None:
	"""通信モジュールの初期化
	・通信回線維持用の別スレッドを起動させる
	"""

	threading.Thread(target=_make_connection_thread, args=()).start()
	time.sleep(1)
