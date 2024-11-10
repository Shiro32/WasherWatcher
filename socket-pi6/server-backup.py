import socket
import threading
import time

send_status = "まだ"
receive_status = "まだ"


# 非同期でデータ受信をひたすら待つ
def receive_message(s):
	global receive_status

	while True:
		try:
			data = s.recv(1024)
			if not data:
				print("クライアントが接続を終了しました。")
				receive_status = "CLOSED"
				break
			receive_status="OPEN"
			print(f"受信: {data.decode()}")
		except ConnectionResetError:
			print("接続がクライアントによってリセットされました。")
			break
		except Exception as e:
			print(f"その他のエラーが発生しました: {e}")
			break

# 非同期でデータ送信
def send_message(s):
	global send_status

	while True:
		try:
			msg = input("サーバー: ")
			if not msg:
				print("送信プロセス終了～")
				send_status = "CLOSED"
				break

			if not s: # 追加: クライアントの接続が存在しない場合
				print("クライアントとの接続がありません。")
				break

			send_status="OEPN"

			if msg=="OPEN":
				print("受信スレッド再起動！")
				threading.Thread(target=receive_message, args=(conn,)).start() 
			else:
				s.sendall(msg.encode())

		except BrokenPipeError:  # この例外をキャッチ
			print("クライアントが接続を終了しました。メッセージの送信ができません。")
			break
		except Exception as e:
			print(f"メッセージ送信時にエラーが発生しました: {e}")
			break
		
		
HOST = '0.0.0.0'
PORT = 65434

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
	print( "通信回線確立待ち" )
	s.bind((HOST, PORT)) #バインディング
	s.listen()  #接続待ち	 s, addr = s.accept()  #接続されたらコネクションとアドレスを取得	 
	conn,adr= s.accept()
	print( "接続完了！" )

	# 受信用と送信用のスレッドを起動
	threading.Thread(target=receive_message, args=(conn,)).start() 
	threading.Thread(target=send_message, args=(conn,)).start()


while True:
	time.sleep(5)
	print( f"【送信：{send_status}】【受信：{receive_status}】" )

