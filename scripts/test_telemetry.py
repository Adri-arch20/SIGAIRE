#!/usr/bin/env python3

import math
import random
import time

import requests

URL = "http://127.0.0.1:5000/api/telemetria"

print("SALUD AMBIENTAL MeteoBot v7.2 - simulador de telemetria")
print("Ctrl+C para terminar.")

pm25 = 12.0
pm10 = 22.0
pm25_filtered = pm25
pm10_filtered = pm10
t = 0.0

try:
    while True:
        pm25_raw = max(0, pm25 + random.uniform(-2.0, 2.0))
        pm10_raw = max(pm25_raw, pm10 + random.uniform(-3.0, 3.0))
        pm25_filtered = 0.35 * pm25_raw + 0.65 * pm25_filtered
        pm10_filtered = 0.35 * pm10_raw + 0.65 * pm10_filtered
        pm25 = max(0, pm25_filtered + random.uniform(-0.2, 0.2))
        pm10 = max(pm25, pm10_filtered + random.uniform(-0.3, 0.3))

        error = math.sin(t) * 85
        obstacle = random.random() < 0.08

        if obstacle:
            movement = "STOP"
            left_pwm = 0
            right_pwm = 0
            object_name = "person"
            object_conf = 0.91
            center_occ = 34.0
            reason = "OBSTACULO"
        elif error > 22:
            movement = "DERECHA"
            left_pwm = 175
            right_pwm = 105
            object_name = ""
            object_conf = 0.0
            center_occ = random.uniform(0, 4)
            reason = "CORREGIR_DERECHA"
        elif error < -22:
            movement = "IZQUIERDA"
            left_pwm = 105
            right_pwm = 175
            object_name = ""
            object_conf = 0.0
            center_occ = random.uniform(0, 4)
            reason = "CORREGIR_IZQUIERDA"
        else:
            movement = "AVANZAR"
            left_pwm = 145
            right_pwm = 145
            object_name = ""
            object_conf = 0.0
            center_occ = random.uniform(0, 3)
            reason = "CENTRADO"

        payload = {
            "robot": "MeteoBot",
            "estado": "online",
            "modo": "autonomo_yolo_bordes_amarillos",
            "movimiento": movement,
            "gesto": "AUTONOMO",
            "esp32": "conectado",
            "vision": {
                "izquierda": random.uniform(0, 5),
                "centro": center_occ,
                "derecha": random.uniform(0, 5),
                "objeto": object_name,
                "confianza": object_conf,
                "brillo": 121,
                "blur": 96,
            },
            "ruta": {
                "estado": "DOS_BORDES",
                "motivo_control": reason,
                "confianza": 0.88,
                "borde_izquierdo_px": 82 + error * 0.15,
                "borde_derecho_px": 558 + error * 0.15,
                "centro_ruta_px": 320 + error,
                "centro_imagen_px": 320,
                "desvio_px": error,
            },
            "motores_visual": {
                "izquierdo": left_pwm,
                "derecho": right_pwm,
                "maximo": 255,
            },
            "yolo": {
                "activo": True,
                "requerido": True,
                "modelo": "yolo11n.pt",
                "obstaculo": obstacle,
            },
            "sensores": {
                "pm25": round(pm25, 1),
                "pm10": round(pm10, 1),
                "pm25_raw": round(pm25_raw, 1),
                "pm10_raw": round(pm10_raw, 1),
                "pm25_filtered": round(pm25_filtered, 1),
                "pm10_filtered": round(pm10_filtered, 1),
                "pm25_std": round(random.uniform(0.2, 1.0), 1),
                "pm10_std": round(random.uniform(0.3, 1.5), 1),
                "pm25_min": round(max(0, pm25_filtered - 1.2), 1),
                "pm25_max": round(pm25_filtered + 1.2, 1),
                "pm10_min": round(max(0, pm10_filtered - 1.8), 1),
                "pm10_max": round(pm10_filtered + 1.8, 1),
                "sds011_estado": "OK",
                "sds011_calibracion": "FABRICA",
                "sds011_muestras": 15,
                "sds011_id": "TEST",
                "sds011_outliers": 0,
                "co2": None,
                "temperatura": None,
                "humedad": None,
                "presion": None,
            },
        }

        response = requests.post(URL, json=payload, timeout=1)
        print(
            f"{movement:9} error={error:6.1f}px "
            f"PWM={left_pwm:3}/{right_pwm:3} "
            f"PM2.5={pm25:5.1f} PM10={pm10:5.1f} -> {response.status_code}"
        )

        t += 0.18
        time.sleep(0.4)

except KeyboardInterrupt:
    print("\nSimulador finalizado.")
