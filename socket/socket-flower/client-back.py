import socket
import threading

def receive_message(s):
    while True:
        try:
            data = s.recv(1024)
            if not data:
                print("サーバーが接続を終了しました。")
                break
            print(f"サーバー: {data.decode()}")
        except ConnectionResetError:
            print("接続がサーバーによってリセットされました。")
            break
        except Exception as e:
            print(f"その他のエラーが発生しました: {e}")
            break

HOST = '192.168.11.20'  # Raspberry PiのIPアドレス
PORT = 65434

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))

    # 受信用のスレッドを起動
    threading.Thread(target=receive_message, args=(s,)).start()

    while True:
        try:
            msg = input("クライアント: ")
            if not msg:
                print("終了～")
                break
            
            s.sendall(msg.encode())
        except Exception as e:
            print(f"メッセージ送信時にエラーが発生しました: {e}")
            break
	
