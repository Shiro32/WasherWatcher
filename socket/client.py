import socket
import threading
import time

#HOST = '192.168.11.25'  # サーバのアドレス
PORT = 65432

comm_status = "close"
count = 0

COMM_GET_WASHER_STATUS = "get_washer_status"
COMM_BEGIN_RAIN_ALERT = "begin_rain_alert"
COMM_END_RAIN_ALERT = "end_rain_alert"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 非同期でデータ受信をひたすら待つ
def receive_message_thread():
	global comm_status, comm_socket, washer_status

	# 通信が確保されている→受信待ちを続ける
	# 通信ができない→スレッド終了
	while True:
		try:
			# 相手からの受信待ち（ブロッキング）
			data = comm_socket.recv(1024)
			if not data:
				print("相手が接続を終了しました。")
				break

			data = data.decode()

			print(f"【受信】 {data}")

			if "hoge" in data:
				send_message( "なんや？" )
			if "rain" in data:
				send_message( "雨降り了解！")

		except ConnectionResetError:
			print("相手によって接続がリセットされました。")
			break
		except Exception as e:
			print(f"その他のエラーが発生しました: {e}")
			break

	# 通信をやめてスレッドを終了する
	comm_socket.close()
	comm_status = "close"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 非同期でデータ送信
def send_message_thread(msg):
	global comm_status, comm_socket

	try:
		if not comm_socket: # クライアントの接続が存在しない場合
			print("親の接続がありません。")
		else:
			#print( f"【送信】:{msg}" )
			comm_socket.sendall(f"{msg}".encode())
			return

	except BrokenPipeError:
		print("サーバが接続を終了しました")

	except Exception as e:
		print(f"メッセージ送信時にエラーが発生しました: {e}")
	
	# 通信をやめてスレッドを終了する
	comm_socket.close()
	comm_status = "close"

def send_message( msg ):
	global comm_socket

	threading.Thread(target=send_message_thread, args=(msg,)).start()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def make_connection():
	global comm_status, comm_socket

	# 一度起動したら決して終了しないで、ずっと通信回線管理
	while True:
		time.sleep(1)

		if( comm_status=="close"):
			host = socket.gethostbyname("zero2.local")
			print(f"Connecting {host}...", end=" " )
			comm_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			
			try:

				comm_socket.connect((host, PORT))
				print( "接続完了！" )
				comm_status = "open"

				# 受信用スレッドを起動
				threading.Thread(target=receive_message_thread, args=()).start() 

			except:
				print("まだや")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 通信回線確立スレッド
threading.Thread(target=make_connection, args=()).start()
time.sleep(5)

while True:
	msg = input( "サーバーへのメッセージ：" )
	if msg:
		send_message(msg)


