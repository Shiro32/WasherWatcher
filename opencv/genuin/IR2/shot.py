import cv2
from picamera2 import Picamera2
from libcamera import controls
import sys

picam2 = Picamera2()
#picam2.configure(picam2.create_preview_configuration(main={"format": 'XRGB8888', "size": (640, 480)}))
#picam2.configure(picam2.create_preview_configuration(main={"format": 'XRGB8888', "size": (1280, 960)    }))
picam2.configure(picam2.create_preview_configuration(main={"format": 'XRGB8888', "size": (2592, 1944)    }))


if( len(sys.argv)!=2 ):
	picam2.start()
	while True:
		im = picam2.capture_array()	#[600:959][0:1279]

		w = im.shape[1]
		h = im.shape[0]
		im = im[int(h/3*2):int(h/3*3), int(w/3*1):int(w/3*2)] #top:bottom, left:right

		cv2.imshow("Camera", im)
		
		key = cv2.waitKey(1)
		if key == 27: break

	picam2.stop()
	cv2.destroyAllWindows()

else:
	picam2.start()
	im = picam2.capture_array()
	im = cv2.cvtColor(im, cv2.COLOR_BGRA2BGR)

	w = im.shape[1]
	h = im.shape[0]
	im = im[int(h/3*2):int(h/3*3), int(w/3*1):int(w/3*2)] #top:bottom, left:right
	cv2.imwrite( sys.argv[1], im )
