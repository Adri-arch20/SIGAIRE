#!/usr/bin/env python3

import os
import signal
import sys
import time
from dataclasses import dataclass

import cv2
import numpy as np
import requests
from picamera2 import Picamera2

from sds011_reader import SDS011Reader

try:
    from ultralytics import YOLO
except Exception:
    YOLO = None


# ============================================================
# SIGAIRE V5 - METEOBOT AUTONOMO
#
# Camara -> bordes amarillos -> correccion diferencial
# YOLO -> deteccion de obstaculos -> STOP de seguridad
# SDS011 -> PM2.5 / PM10
# Todo -> SALUD AMBIENTAL -> WebSocket + SQLite
# ============================================================


# ============================================================
# RED
# ============================================================

ESP32_IP = os.getenv("METEOBOT_ESP32_IP", "192.168.137.200")
SIGAIRE_URL = os.getenv(
    "SIGAIRE_TELEMETRY_URL",
    "http://127.0.0.1:5000/api/telemetria",
)
DASHBOARD_URL = os.getenv(
    "SIGAIRE_DASHBOARD_URL",
    "http://127.0.0.1:5000/",
)

URL_MOTORES = f"http://{ESP32_IP}/motores"
URL_STOP = f"http://{ESP32_IP}/stop"


# ============================================================
# SDS011
# ============================================================

SDS011_PORT = None


# ============================================================
# CAMARA
# ============================================================

ANCHO = 640
ALTO = 480
FPS = 30
MOSTRAR_CAMARA = True

# Valores base de libcamera. No se aplica aumento artificial de brillo
# ni de nitidez. La exposicion y balance de blancos siguen automaticos.
CAMERA_BRIGHTNESS = 0.0
CAMERA_SHARPNESS = 1.0


# ============================================================
# RUTA AMARILLA
# ============================================================

HSV_AMARILLO_BAJO = np.array([15, 70, 100], dtype=np.uint8)
HSV_AMARILLO_ALTO = np.array([42, 255, 255], dtype=np.uint8)
ROI_RUTA_INICIO = 0.42
FRACCION_CENTRO_IZQ = 0.49
FRACCION_CENTRO_DER = 0.51
MIN_FILAS_BORDE = 18
MIN_CONFIANZA_RUTA = 0.26
ANCHO_CARRIL_INICIAL = 0.72
SUAVIZADO_CENTRO = 0.72
SUAVIZADO_ANCHO = 0.86

DEADBAND_PX = 22
PWM_BASE = 145
PWM_MIN_AVANCE = 75
PWM_MAX = 185
KP_GIRO = 0.55
MAX_CORRECCION = 82


# ============================================================
# YOLO / OBSTACULOS
# ============================================================

YOLO_MODEL = os.getenv("METEOBOT_YOLO_MODEL", "yolo11n.pt")
YOLO_CONF = float(os.getenv("METEOBOT_YOLO_CONF", "0.38"))
YOLO_IMGSZ = int(os.getenv("METEOBOT_YOLO_IMGSZ", "416"))
YOLO_CADA_N_FRAMES = int(os.getenv("METEOBOT_YOLO_EVERY", "3"))
YOLO_REQUERIDO = os.getenv("METEOBOT_REQUIRE_YOLO", "1") != "0"

# Clases COCO que se consideran obstaculos relevantes en un recorrido.
OBSTACLE_NAMES = {
    "person",
    "bicycle",
    "car",
    "motorcycle",
    "bus",
    "truck",
    "dog",
    "cat",
    "bench",
    "chair",
    "backpack",
    "suitcase",
}

CENTRAL_X1 = 0.24
CENTRAL_X2 = 0.76
RIESGO_AREA_MIN = 0.012
RIESGO_Y2_MIN = 0.54


# ============================================================
# COMUNICACION
# ============================================================

INTERVALO_MOTOR = 0.20
INTERVALO_SIGAIRE = 0.40
TIMEOUT_HTTP = 0.35


# ============================================================
# ESTADO GLOBAL
# ============================================================

estado = "STOP"
esp32_estado = "desconectado"
ultimo_motor = 0.0
ultimo_sigaire = 0.0
ejecutando = True
picam2 = None
sds011 = None
yolo_model = None


@dataclass
class RouteState:
    left_x: float | None
    right_x: float | None
    center_x: float | None
    confidence: float
    error_px: float
    status: str
    mask: np.ndarray


@dataclass
class ObstacleState:
    blocked: bool
    name: str
    confidence: float
    zone_left: float
    zone_center: float
    zone_right: float
    detections: list
    yolo_ready: bool


class YellowRouteTracker:
    def __init__(self, width: int) -> None:
        self.width = width
        self.lane_width = width * ANCHO_CARRIL_INICIAL
        self.center = width / 2.0

    @staticmethod
    def _rows_to_boundary(mask: np.ndarray, width: int):
        h = mask.shape[0]
        y0 = int(h * 0.56)
        y1 = int(h * 0.95)
        left_rows = []
        right_rows = []

        for y in range(y0, y1, 2):
            xs = np.flatnonzero(mask[y] > 0)
            if xs.size == 0:
                continue

            left = xs[xs < int(width * FRACCION_CENTRO_IZQ)]
            right = xs[xs > int(width * FRACCION_CENTRO_DER)]

            if left.size:
                left_rows.append(float(left.max()))

            if right.size:
                right_rows.append(float(right.min()))

        total_rows = max(1, (y1 - y0) // 2)
        return left_rows, right_rows, total_rows

    def analyze(self, frame_rgb: np.ndarray) -> RouteState:
        bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        h, w = bgr.shape[:2]
        roi_y = int(h * ROI_RUTA_INICIO)
        roi = bgr[roi_y:, :]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        mask = cv2.inRange(hsv, HSV_AMARILLO_BAJO, HSV_AMARILLO_ALTO)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        left_rows, right_rows, total_rows = self._rows_to_boundary(mask, w)
        left_x = float(np.median(left_rows)) if len(left_rows) >= MIN_FILAS_BORDE else None
        right_x = float(np.median(right_rows)) if len(right_rows) >= MIN_FILAS_BORDE else None

        conf_left = min(1.0, len(left_rows) / total_rows)
        conf_right = min(1.0, len(right_rows) / total_rows)

        if left_x is not None and right_x is not None:
            measured_width = right_x - left_x

            if 0.34 * w <= measured_width <= 0.98 * w:
                self.lane_width = (
                    SUAVIZADO_ANCHO * self.lane_width
                    + (1.0 - SUAVIZADO_ANCHO) * measured_width
                )
                raw_center = (left_x + right_x) / 2.0
                confidence = min(conf_left, conf_right)
                status = "DOS_BORDES"
            else:
                raw_center = self.center
                confidence = 0.0
                status = "ANCHO_INVALIDO"

        elif left_x is not None:
            raw_center = left_x + self.lane_width / 2.0
            confidence = conf_left * 0.70
            status = "BORDE_IZQUIERDO"

        elif right_x is not None:
            raw_center = right_x - self.lane_width / 2.0
            confidence = conf_right * 0.70
            status = "BORDE_DERECHO"

        else:
            raw_center = None
            confidence = 0.0
            status = "SIN_RUTA"

        if raw_center is not None:
            raw_center = float(np.clip(raw_center, 0, w - 1))
            self.center = (
                SUAVIZADO_CENTRO * self.center
                + (1.0 - SUAVIZADO_CENTRO) * raw_center
            )
            center_x = self.center
            error_px = center_x - (w / 2.0)
        else:
            center_x = None
            error_px = 0.0

        return RouteState(
            left_x=left_x,
            right_x=right_x,
            center_x=center_x,
            confidence=float(confidence),
            error_px=float(error_px),
            status=status,
            mask=mask,
        )


# ============================================================
# ESP32
# ============================================================


def post_esp32(url: str, params=None) -> bool:
    global esp32_estado

    try:
        response = requests.post(
            url,
            params=params,
            timeout=TIMEOUT_HTTP,
        )

        if response.status_code == 200:
            esp32_estado = "conectado"
            return True

    except requests.RequestException:
        pass

    esp32_estado = "desconectado"
    return False


def enviar_motores(left_pwm: int, right_pwm: int) -> bool:
    return post_esp32(
        URL_MOTORES,
        params={
            "izq": int(left_pwm),
            "der": int(right_pwm),
        },
    )


def enviar_stop() -> bool:
    return post_esp32(URL_STOP)


# ============================================================
# YOLO
# ============================================================


def cargar_yolo():
    global yolo_model

    if YOLO is None:
        print("[YOLO] ultralytics no esta instalado.")
        return False

    try:
        yolo_model = YOLO(YOLO_MODEL)
        print(f"[YOLO] Modelo cargado: {YOLO_MODEL}")
        return True
    except Exception as exc:
        print(f"[YOLO] No se pudo cargar el modelo: {exc}")
        yolo_model = None
        return False


def _intersection_area(box, x1, y1, x2, y2):
    bx1, by1, bx2, by2 = box
    ix1 = max(bx1, x1)
    iy1 = max(by1, y1)
    ix2 = min(bx2, x2)
    iy2 = min(by2, y2)
    return max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)


def detectar_obstaculos(frame_rgb: np.ndarray) -> ObstacleState:
    h, w = frame_rgb.shape[:2]

    if yolo_model is None:
        return ObstacleState(
            blocked=YOLO_REQUERIDO,
            name="YOLO_NO_DISPONIBLE" if YOLO_REQUERIDO else "",
            confidence=0.0,
            zone_left=0.0,
            zone_center=0.0,
            zone_right=0.0,
            detections=[],
            yolo_ready=False,
        )

    bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

    try:
        result = yolo_model.predict(
            source=bgr,
            imgsz=YOLO_IMGSZ,
            conf=YOLO_CONF,
            verbose=False,
            device="cpu",
        )[0]
    except Exception as exc:
        print(f"\n[YOLO] Error de inferencia: {exc}")
        return ObstacleState(
            blocked=YOLO_REQUERIDO,
            name="YOLO_ERROR" if YOLO_REQUERIDO else "",
            confidence=0.0,
            zone_left=0.0,
            zone_center=0.0,
            zone_right=0.0,
            detections=[],
            yolo_ready=False,
        )

    zones = [0.0, 0.0, 0.0]
    zone_edges = [0, w / 3.0, 2 * w / 3.0, w]
    zone_area = (w / 3.0) * h

    detections = []
    blocked = False
    primary_name = ""
    primary_conf = 0.0
    primary_score = 0.0

    names = result.names

    if result.boxes is not None:
        xyxy = result.boxes.xyxy.cpu().numpy()
        confs = result.boxes.conf.cpu().numpy()
        classes = result.boxes.cls.cpu().numpy().astype(int)

        for box, conf, class_id in zip(xyxy, confs, classes):
            x1, y1, x2, y2 = [float(v) for v in box]
            name = str(names.get(class_id, class_id))

            if name not in OBSTACLE_NAMES:
                continue

            area_ratio = max(0.0, (x2 - x1) * (y2 - y1)) / float(w * h)
            center_overlap = _intersection_area(
                (x1, y1, x2, y2),
                w * CENTRAL_X1,
                0,
                w * CENTRAL_X2,
                h,
            )
            box_area = max(1.0, (x2 - x1) * (y2 - y1))
            center_overlap_ratio = center_overlap / box_area

            risky = (
                center_overlap_ratio > 0.22
                and y2 >= h * RIESGO_Y2_MIN
                and area_ratio >= RIESGO_AREA_MIN
            )

            if risky:
                blocked = True

            score = area_ratio * (0.6 + center_overlap_ratio)

            if score > primary_score:
                primary_score = score
                primary_name = name
                primary_conf = float(conf)

            detections.append(
                {
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "name": name,
                    "confidence": float(conf),
                    "risky": risky,
                }
            )

            for idx in range(3):
                zone_x1 = zone_edges[idx]
                zone_x2 = zone_edges[idx + 1]
                zones[idx] += _intersection_area(
                    (x1, y1, x2, y2),
                    zone_x1,
                    0,
                    zone_x2,
                    h,
                )

    zones_pct = [min(100.0, 100.0 * value / zone_area) for value in zones]

    return ObstacleState(
        blocked=blocked,
        name=primary_name,
        confidence=primary_conf,
        zone_left=zones_pct[0],
        zone_center=zones_pct[1],
        zone_right=zones_pct[2],
        detections=detections,
        yolo_ready=True,
    )


# ============================================================
# CONTROL AUTONOMO
# ============================================================


def calcular_movimiento(route: RouteState, obstacle: ObstacleState):
    if not obstacle.yolo_ready and YOLO_REQUERIDO:
        return "STOP", 0, 0, "YOLO_NO_DISPONIBLE"

    if obstacle.blocked:
        return "STOP", 0, 0, "OBSTACULO"

    if route.center_x is None or route.confidence < MIN_CONFIANZA_RUTA:
        return "STOP", 0, 0, "RUTA_NO_CONFIABLE"

    error = route.error_px

    if abs(error) <= DEADBAND_PX:
        return "AVANZAR", PWM_BASE, PWM_BASE, "CENTRADO"

    correction = int(np.clip(KP_GIRO * abs(error), 0, MAX_CORRECCION))

    if error > 0:
        left = min(PWM_MAX, PWM_BASE + correction)
        right = max(PWM_MIN_AVANCE, PWM_BASE - correction)
        return "DERECHA", left, right, "CORREGIR_DERECHA"

    left = max(PWM_MIN_AVANCE, PWM_BASE - correction)
    right = min(PWM_MAX, PWM_BASE + correction)
    return "IZQUIERDA", left, right, "CORREGIR_IZQUIERDA"


# ============================================================
# CALIDAD DE IMAGEN
# ============================================================


def calidad_imagen(frame_rgb: np.ndarray):
    gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
    brightness = float(np.mean(gray))
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    return brightness, sharpness


# ============================================================
# SIGAIRE
# ============================================================


def enviar_sigaire(
    movimiento: str,
    reason: str,
    left_pwm: int,
    right_pwm: int,
    route: RouteState,
    obstacle: ObstacleState,
    brightness: float,
    sharpness: float,
    sensor_data: dict,
):
    payload = {
        "robot": "MeteoBot",
        "estado": "online",
        "modo": "autonomo_yolo_bordes_amarillos",
        "movimiento": movimiento,
        # Se conserva este campo por compatibilidad con la base v4.
        # Ya no representa un gesto de mano.
        "gesto": "AUTONOMO",
        "esp32": esp32_estado,
        "vision": {
            "izquierda": obstacle.zone_left,
            "centro": obstacle.zone_center,
            "derecha": obstacle.zone_right,
            "objeto": obstacle.name,
            "confianza": obstacle.confidence,
            "brillo": float(brightness),
            "blur": float(sharpness),
        },
        "ruta": {
            "estado": route.status,
            "motivo_control": reason,
            "confianza": route.confidence,
            "borde_izquierdo_px": route.left_x,
            "borde_derecho_px": route.right_x,
            "centro_ruta_px": route.center_x,
            "centro_imagen_px": ANCHO / 2.0,
            "desvio_px": route.error_px,
            "amarillo_h_min": int(HSV_AMARILLO_BAJO[0]),
            "amarillo_h_max": int(HSV_AMARILLO_ALTO[0]),
        },
        # Solo telemetria visual para SIGAIRE. La pagina NO usa estos
        # valores para mandar ordenes a los motores.
        "motores_visual": {
            "izquierdo": int(left_pwm),
            "derecho": int(right_pwm),
            "maximo": 255,
        },
        "yolo": {
            "activo": obstacle.yolo_ready,
            "requerido": YOLO_REQUERIDO,
            "modelo": YOLO_MODEL,
            "obstaculo": obstacle.blocked,
        },
        "sensores": {
            "pm25": sensor_data.get("pm25"),
            "pm10": sensor_data.get("pm10"),
            "pm25_raw": sensor_data.get("pm25_raw"),
            "pm10_raw": sensor_data.get("pm10_raw"),
            "pm25_filtered": sensor_data.get("pm25_filtered"),
            "pm10_filtered": sensor_data.get("pm10_filtered"),
            "pm25_std": sensor_data.get("pm25_std"),
            "pm10_std": sensor_data.get("pm10_std"),
            "pm25_min": sensor_data.get("pm25_min"),
            "pm25_max": sensor_data.get("pm25_max"),
            "pm10_min": sensor_data.get("pm10_min"),
            "pm10_max": sensor_data.get("pm10_max"),
            "sds011_estado": sensor_data.get("sds011_estado", "SIN_DATOS"),
            "sds011_calibracion": sensor_data.get("sds011_calibracion", "FABRICA"),
            "sds011_muestras": sensor_data.get("sds011_muestras", 0),
            "sds011_outliers": sensor_data.get("sds011_outliers", 0),
            "sds011_id": sensor_data.get("sds011_id", ""),
            "sds011_puerto": sensor_data.get("sds011_puerto", ""),
            "sds011_calentamiento_restante": sensor_data.get(
                "sds011_calentamiento_restante"
            ),
            "sds011_edad_lectura_s": sensor_data.get("sds011_edad_lectura_s"),
            "co2": None,
            "temperatura": None,
            "humedad": None,
            "presion": None,
        },
    }

    try:
        requests.post(
            SIGAIRE_URL,
            json=payload,
            timeout=0.25,
        )
    except requests.RequestException:
        pass


# ============================================================
# CAMARA
# ============================================================


def iniciar_camara():
    global picam2

    picam2 = Picamera2()
    config = picam2.create_video_configuration(
        main={
            "format": "RGB888",
            "size": (ANCHO, ALTO),
        },
        controls={
            "FrameRate": FPS,
            "Brightness": CAMERA_BRIGHTNESS,
            "Sharpness": CAMERA_SHARPNESS,
        },
    )
    picam2.configure(config)
    picam2.start()
    time.sleep(1.5)


# ============================================================
# VISTA LOCAL
# ============================================================


def dibujar_vista(
    frame_rgb: np.ndarray,
    route: RouteState,
    obstacle: ObstacleState,
    movement: str,
    left_pwm: int,
    right_pwm: int,
    sensor_data: dict,
):
    view = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    h, w = view.shape[:2]
    roi_y = int(h * ROI_RUTA_INICIO)

    overlay = view.copy()
    yellow = np.zeros_like(view[roi_y:])
    yellow[:, :, 1] = route.mask
    yellow[:, :, 2] = route.mask
    overlay[roi_y:] = cv2.addWeighted(view[roi_y:], 0.82, yellow, 0.35, 0)
    view = overlay

    if route.left_x is not None:
        cv2.circle(view, (int(route.left_x), int(h * 0.82)), 8, (0, 255, 255), -1)

    if route.right_x is not None:
        cv2.circle(view, (int(route.right_x), int(h * 0.82)), 8, (0, 255, 255), -1)

    if route.center_x is not None:
        cv2.line(
            view,
            (int(route.center_x), int(h * 0.60)),
            (int(route.center_x), h - 1),
            (255, 255, 0),
            3,
        )

    cv2.line(view, (w // 2, int(h * 0.55)), (w // 2, h - 1), (255, 255, 255), 1)

    for det in obstacle.detections:
        x1 = int(det["x1"])
        y1 = int(det["y1"])
        x2 = int(det["x2"])
        y2 = int(det["y2"])
        color = (0, 0, 255) if det["risky"] else (0, 190, 255)
        cv2.rectangle(view, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            view,
            f"{det['name']} {det['confidence']:.2f}",
            (x1, max(18, y1 - 7)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            color,
            2,
        )

    pm25 = sensor_data.get("pm25")
    pm10 = sensor_data.get("pm10")
    pm25_txt = "--" if pm25 is None else f"{pm25:.1f}"
    pm10_txt = "--" if pm10 is None else f"{pm10:.1f}"

    status_color = (0, 0, 255) if movement == "STOP" else (0, 255, 0)
    lines = [
        f"AUTO: {movement}",
        f"PWM I/D: {left_pwm}/{right_pwm}",
        f"RUTA: {route.status} conf={route.confidence:.2f} err={route.error_px:.0f}px",
        f"YOLO: {'OK' if obstacle.yolo_ready else 'NO'} obj={obstacle.name or '-'}",
        f"PM2.5={pm25_txt}  PM10={pm10_txt} ug/m3",
    ]

    for idx, text in enumerate(lines):
        cv2.putText(
            view,
            text,
            (14, 30 + idx * 27),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            status_color if idx == 0 else (255, 255, 255),
            2,
        )

    return view


# ============================================================
# PARADA SEGURA
# ============================================================


def parada_segura():
    global ejecutando
    ejecutando = False

    for _ in range(3):
        try:
            requests.post(URL_STOP, timeout=0.20)
        except requests.RequestException:
            pass
        time.sleep(0.05)


def manejar_senal(signum, frame):
    print(f"\n[SISTEMA] Senal {signum}. STOP de seguridad.")
    parada_segura()


signal.signal(signal.SIGINT, manejar_senal)
signal.signal(signal.SIGTERM, manejar_senal)


# ============================================================
# PRINCIPAL
# ============================================================


def main():
    global estado
    global ultimo_motor
    global ultimo_sigaire
    global sds011

    print()
    print("==================================================")
    print(" SIGAIRE V5 - METEOBOT AUTONOMO")
    print("==================================================")
    print(f"ESP32:     {ESP32_IP}")
    print(f"Dashboard: {DASHBOARD_URL}")
    print(f"YOLO:      {YOLO_MODEL}")
    print()
    print("RUTA AMARILLA -> direccion autonoma")
    print("YOLO + obstaculo frontal -> STOP")
    print("SDS011 -> PM2.5 / PM10 -> SIGAIRE")
    print()

    sds011 = SDS011Reader(port=SDS011_PORT)
    sds011.start()
    print(f"SDS011: {sds011.port}")

    yolo_ok = cargar_yolo()
    if not yolo_ok and YOLO_REQUERIDO:
        print("[SEGURIDAD] YOLO es obligatorio: el robot permanecera en STOP.")

    iniciar_camara()
    tracker = YellowRouteTracker(ANCHO)
    enviar_stop()

    frame_index = 0
    last_obstacle = ObstacleState(
        blocked=YOLO_REQUERIDO and not yolo_ok,
        name="YOLO_NO_DISPONIBLE" if YOLO_REQUERIDO and not yolo_ok else "",
        confidence=0.0,
        zone_left=0.0,
        zone_center=0.0,
        zone_right=0.0,
        detections=[],
        yolo_ready=yolo_ok,
    )

    while ejecutando:
        frame = picam2.capture_array()
        route = tracker.analyze(frame)

        if frame_index % max(1, YOLO_CADA_N_FRAMES) == 0:
            last_obstacle = detectar_obstaculos(frame)

        obstacle = last_obstacle
        brightness, sharpness = calidad_imagen(frame)
        movement, left_pwm, right_pwm, reason = calcular_movimiento(route, obstacle)
        estado = movement
        now = time.monotonic()

        if now - ultimo_motor >= INTERVALO_MOTOR:
            if movement == "STOP":
                enviar_stop()
            else:
                ok = enviar_motores(left_pwm, right_pwm)
                if not ok:
                    movement = "STOP"
                    estado = "STOP"
                    left_pwm = 0
                    right_pwm = 0
                    reason = "ESP32_SIN_RESPUESTA"
                    enviar_stop()

            ultimo_motor = now

        sensor_data = sds011.snapshot()

        if now - ultimo_sigaire >= INTERVALO_SIGAIRE:
            enviar_sigaire(
                movimiento=movement,
                reason=reason,
                left_pwm=left_pwm,
                right_pwm=right_pwm,
                route=route,
                obstacle=obstacle,
                brightness=brightness,
                sharpness=sharpness,
                sensor_data=sensor_data,
            )
            ultimo_sigaire = now

        pm25 = sensor_data.get("pm25")
        pm10 = sensor_data.get("pm10")
        pm25_txt = "--" if pm25 is None else f"{pm25:.1f}"
        pm10_txt = "--" if pm10 is None else f"{pm10:.1f}"

        print(
            f"\rAUTO={movement:9} | "
            f"RUTA={route.status:16} | "
            f"ERR={route.error_px:6.0f}px | "
            f"PWM={left_pwm:3}/{right_pwm:3} | "
            f"OBJ={obstacle.name or '-':18} | "
            f"ESP32={esp32_estado:12} | "
            f"PM2.5={pm25_txt:>6} | PM10={pm10_txt:>6}",
            end="",
            flush=True,
        )

        if MOSTRAR_CAMARA:
            view = dibujar_vista(
                frame,
                route,
                obstacle,
                movement,
                left_pwm,
                right_pwm,
                sensor_data,
            )
            cv2.imshow("SIGAIRE - MeteoBot Autonomo", view)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        frame_index += 1


if __name__ == "__main__":
    try:
        main()
    finally:
        parada_segura()

        if sds011 is not None:
            sds011.stop()

        if picam2 is not None:
            try:
                picam2.stop()
            except Exception:
                pass

        cv2.destroyAllWindows()

        try:
            requests.post(
                SIGAIRE_URL,
                json={
                    "robot": "MeteoBot",
                    "estado": "offline",
                    "modo": "autonomo_yolo_bordes_amarillos",
                    "movimiento": "STOP",
                    "gesto": "AUTONOMO",
                    "esp32": esp32_estado,
                    "vision": {
                        "izquierda": 0,
                        "centro": 0,
                        "derecha": 0,
                        "objeto": "",
                        "confianza": 0,
                        "brillo": 0,
                        "blur": 0,
                    },
                    "ruta": {
                        "estado": "DETENIDO",
                        "motivo_control": "SALIDA_SEGURA",
                        "confianza": 0,
                        "desvio_px": 0,
                    },
                    "motores_visual": {
                        "izquierdo": 0,
                        "derecho": 0,
                        "maximo": 255,
                    },
                    "yolo": {
                        "activo": yolo_model is not None,
                        "requerido": YOLO_REQUERIDO,
                        "modelo": YOLO_MODEL,
                        "obstaculo": False,
                    },
                    "sensores": (
                        sds011.snapshot()
                        if sds011 is not None
                        else {
                            "pm25": None,
                            "pm10": None,
                            "sds011_estado": "SIN_DATOS",
                        }
                    ),
                },
                timeout=0.20,
            )
        except requests.RequestException:
            pass

        print("\nMeteoBot detenido de forma segura.")
        sys.exit(0)
