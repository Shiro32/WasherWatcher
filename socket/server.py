import socket
import threading
import time
import sys
import keyboard

HOST = '0.0.0.0'
PORT = 65432


comm_status = "close"
count = 0


# 非同期でデータ受信をひたすら待つ
def receive_message(s):
	global comm_status

	while True:
		try:
			data = s.recv(1024)	# ココデブロッキング
			if not data:
				print("クライアントが接続を終了しました。")
				break

			print(f"【受信】 {data.decode()}")
		except ConnectionResetError:
			print("接続がクライアントによってリセットされました。")
			break
		except Exception as e:
			print(f"その他のエラーが発生しました: {e}")
			break

	# whileループの外側
	s.close()
	comm_status = "close"


# 非同期でデータ送信
def send_message(s):
	global comm_status, count

	while True:
		count+=1
		time.sleep(5)

		#if count>=5:
		#	print("切断試験")
		#	break;

		try:
			if not s: # クライアントの接続が存在しない場合
				print("クライアントとの接続がありません。")
				break

			msg = "親→子"+str(count)
			print(f"【送信】{msg}")
			s.sendall(msg.encode())

		except BrokenPipeError:  # この例外をキャッチ
			print("クライアントが接続を終了しました。メッセージの送信ができません。")
			break
		except Exception as e:
			print(f"メッセージ送信時にエラーが発生しました: {e}")
			break
	
	s.close()
	comm_status = "close"
		

while True:
	#接続処理
	if( comm_status=="close"):
		print("再接続・・・" )
		sock=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		sock.bind((HOST, PORT))	#バインディング
		sock.listen()				#接続待ち
		conn,adr= sock.accept()	#接続確立（ここは非ブロッキング）
		print( "接続完了！" )

		comm_status = "open"
		# 受信用と送信用のスレッドを起動
		threading.Thread(target=receive_message, args=(conn,)).start() 
		threading.Thread(target=send_message, args=(conn,)).start()


		time.sleep(5)

	#print( f"【SOCKET】{comm_status}" )

