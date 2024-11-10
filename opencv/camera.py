import cv2
from picamera2 import Picamera2

# カメラ準備 
cap = cv2.VideoCapture(1)
 
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)


# 無限ループ 
while True:
    # キー押下で終了 
    key = cv2.waitKey(1)
    if key != -1:
        break
 
    # カメラ画像読み込み 
    ret, frame = cap.read()
 
	# 画像表示 
    cv2.imshow('image', frame)
 
# 終了処理 
cap.release()
cv2.destroyAllWindows()
