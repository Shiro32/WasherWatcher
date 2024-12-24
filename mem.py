import sys
import cv2
import numpy as np
from picamera2 import Picamera2


from itertools import chain
from collections import deque


def total_size(obj, verbose=False):
    seen = set()

    def sizeof(o):
        if id(o) in seen:
            return 0
        seen.add(id(o))
        s = sys.getsizeof(o, default=0)
        if verbose:
            print(s, type(o), repr(o))
        if isinstance(o, (tuple, list, set, frozenset, deque)):
            s += sum(map(sizeof, iter(o)))
        elif isinstance(o, dict):
            s += sum(map(sizeof, chain.from_iterable(o.items())))
        elif "__dict__" in dir(o):  # もっと良い方法はあるはず
            s += sum(map(sizeof, chain.from_iterable(o.__dict__.items())))
        return s

    return sizeof(obj)


CAPTURE_WIDTH	= 2592
CAPTURE_HEIGHT	= 1944
#CAPTURE_WIDTH	= 1280 #2592
#CAPTURE_HEIGHT	= 960 #1944

picam = Picamera2()

picam.configure(
	picam.create_preview_configuration(
		main={"format": 'XRGB8888', "size": (CAPTURE_WIDTH, CAPTURE_HEIGHT)}))

picam.start()
img = picam.capture_array()

print( img.nbytes )

picam.stop()


