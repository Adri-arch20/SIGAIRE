#!/usr/bin/env python3

import time

import cv2
import numpy as np
from picamera2 import Picamera2

ANCHO = 640
ALTO = 480
FPS = 30
HSV_BAJO = np.array([15, 70, 100], dtype=np.uint8)
HSV_ALTO = np.array([42, 255, 255], dtype=np.uint8)
ROI_INICIO = 0.42


def detectar(frame_rgb):
    bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    h, w = bgr.shape[:2]
    y0 = int(h * ROI_INICIO)
    roi = bgr[y0:]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, HSV_BAJO, HSV_ALTO)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    row_start = int(mask.shape[0] * 0.56)
    row_end = int(mask.shape[0] * 0.95)
    left = []
    right = []

    for y in range(row_start, row_end, 2):
        xs = np.flatnonzero(mask[y] > 0)
        l = xs[xs < int(w * 0.49)]
        r = xs[xs > int(w * 0.51)]

        if l.size:
            left.append(float(l.max()))
        if r.size:
            right.append(float(r.min()))

    lx = float(np.median(left)) if len(left) >= 18 else None
    rx = float(np.median(right)) if len(right) >= 18 else None
    center = (lx + rx) / 2 if lx is not None and rx is not None else None

    return bgr, mask, y0, lx, rx, center


def main():
    camera = Picamera2()
    config = camera.create_video_configuration(
        main={"format": "RGB888", "size": (ANCHO, ALTO)},
        controls={"FrameRate": FPS, "Brightness": 0.0, "Sharpness": 1.0},
    )
    camera.configure(config)
    camera.start()
    time.sleep(1.5)

    try:
        while True:
            frame = camera.capture_array()
            view, mask, roi_y, lx, rx, center = detectar(frame)
            h, w = view.shape[:2]

            cv2.line(view, (w // 2, roi_y), (w // 2, h - 1), (255, 255, 255), 2)

            if lx is not None:
                cv2.circle(view, (int(lx), int(h * 0.80)), 9, (0, 255, 255), -1)
            if rx is not None:
                cv2.circle(view, (int(rx), int(h * 0.80)), 9, (0, 255, 255), -1)
            if center is not None:
                cv2.line(view, (int(center), roi_y), (int(center), h - 1), (255, 255, 0), 3)
                error = center - w / 2
                cv2.putText(
                    view,
                    f"Centro ruta={center:.0f}px  error={error:.0f}px",
                    (15, 35),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (255, 255, 255),
                    2,
                )
            else:
                cv2.putText(
                    view,
                    "No se detectan ambos bordes",
                    (15, 35),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (0, 0, 255),
                    2,
                )

            cv2.imshow("Prueba bordes amarillos - SIN MOTORES", view)
            cv2.imshow("Mascara amarilla", mask)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        camera.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
