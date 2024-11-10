import cv2
import numpy as np

img = cv2.imread("on.png")
tpl = cv2.imread("off_tmpl.png")

#パターンマッチ
result = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)

ys, xs = np.where(result >= 0.95)

dst = img.copy()
for x, y in zip(xs, ys):
    cv2.rectangle(
        dst,
        (x, y),
        (x + tpl.shape[1], y + tpl.shape[0]),
        color=(0, 255, 0),
        thickness=2,
    )


print( f"Match count:{len(ys)}")
if ys: print("hoge")


cv2.imshow("frame", dst)

cv2.waitKey(0)
cv2.destroyAllWindows()
