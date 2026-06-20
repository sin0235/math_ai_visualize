from __future__ import annotations


def preprocess_for_ocr(image):
    try:
        import cv2
        import numpy as np
    except ImportError:
        return image

    array = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape[:2]
    scale = 2 if max(width, height) < 1200 else 1
    if scale > 1:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
    gray = cv2.equalizeHist(gray)
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11)
    return binary
