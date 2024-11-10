import socket
import threading
import time

HOST = '192.168.11.20'  # Raspberry PiのIPアドレス
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
def send_message(sock):
	global comm_status, count

	while True:
		time.sleep(2)
		count+=1

		try:
			if not sock: # クライアントの接続が存在しない場合
				print("親の接続がありません。")
				break

			print( f"【送信】子→親{count}" )
			sock.sendall(f"子→親{count}".encode())

		except BrokenPipeError:  # この例外をキャッチ
			print("親が接続を終了しました。メッセージの送信ができません。")
			break
		except Exception as e:
			print(f"メッセージ送信時にエラーが発生しました: {e}")
			break
	
	sock.close()
	comm_status = "close"
		

while True:

	#接続処理
	if( comm_status=="close"):
		print("再接続・・・", end=" " )

		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		
		try:
			sock.connect((HOST, PORT))
			print( "接続完了！" )
			comm_status = "open"

			# 受信用と送信用のスレッドを起動
			threading.Thread(target=receive_message, args=(sock,)).start() 
			threading.Thread(target=send_message, args=(sock,)).start()

		except:
			print("まだや")

	time.sleep(5)
	#print( f"【SOCKET】{comm_status}" )


