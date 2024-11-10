import cv2
import numpy as np

image_file = 'led.png'
frame	= cv2.imread(image_file)
hsv		= cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

lower	= np.array([0,100,200])
upper	= np.array([30,255,255])

mask	= cv2.inRange(hsv, lower, upper)
res		= cv2.bitwise_and(frame, frame, mask=mask)

# 合体！
ledarea = cv2.countNonZero(mask)
if ledarea >= 0:
	cv2.putText(res, "RED :"+str(ledarea)+" pixels", (200,200), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2, cv2.LINE_AA)

cv2.imshow('res', res)
cv2.imshow('frame', frame)

cv2.waitKey(0)
cv2.destroyAllWindows()
