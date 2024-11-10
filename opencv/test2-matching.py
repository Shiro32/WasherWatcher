import cv2
import numpy as np

img = cv2.imread("off.png")
tpl = cv2.imread("on_tmpl.png")

#パターンマッチ
result = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)

#結果位置
minVal, maxVal, minLoc, maxLoc = cv2.minMaxLoc(result)

tl = maxLoc[0], maxLoc[1]
br = maxLoc[0]+tpl.shape[1], maxLoc[1]+tpl.shape[0]

dst = img.copy()
cv2.rectangle(dst, tl, br, color=(0,255,0), thickness=2)

cv2.imshow("frame", dst)

cv2.waitKey(0)
cv2.destroyAllWindows()
