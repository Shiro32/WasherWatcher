import cv2
import numpy as np

image_file = 'led.png'
frame	= cv2.imread(image_file)
cv2.imshow('frame', frame)

cv2.waitKey(0)
cv2.destroyAllWindows()
