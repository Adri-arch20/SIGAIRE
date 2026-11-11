#!/usr/bin/env python3
"""Simulador visual de SALUD AMBIENTAL.

Publica datos de prueba en el backend local sin enviar órdenes de movimiento
al ESP32. Sirve para validar la nueva interfaz antes de conectar hardware.
Ctrl+C para detener.
"""
import json
import math
import random
import time
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:5000"


def post(path, payload):
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        BASE + path,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urlopen(request, timeout=2) as response:
        return json.load(response)


def main():
    print("SALUD AMBIENTAL · simulación de sensores")
    print("No envía órdenes a motores ni al ESP32.")
    print("Abre http://localhost:5000 y presiona Ctrl+C para terminar.\n")

    tick = 0
    while True:
        phase = tick / 10
        pm25 = max(2, 14 + 7 * math.sin(phase) + random.uniform(-1.5, 1.5))
        pm10 = max(5, 32 + 14 * math.sin(phase * 0.72 + 0.8) + random.uniform(-2, 2))
        temp = 23.5 + 2.2 * math.sin(phase * 0.35)
        hum = 56 + 5 * math.sin(phase * 0.27 + 1.2)
        sharp_v = 0.44 + 0.025 * math.sin(phase * 1.15)
        bfs_v = 1.18 + 0.08 * math.sin(phase * 0.55)
        co2_ppm = 610 + 75 * math.sin(phase * 0.23)
        mg811_aout = 0.292 + 0.012 * math.sin(phase * 0.23)

        telemetry = {
            "robot": "MeteoBot",
            "estado": "online",
            "modo": "simulacion_salud_ambiental",
            "movimiento": "STOP",
            "gesto": "AUTONOMO",
            "esp32": "conectado",
            "vision": {"objeto": "", "confianza": 0, "brillo": 0, "blur": 0},
            "sensores": {
                "pm25": round(pm25, 2),
                "pm10": round(pm10, 2),
                "pm25_filtered": round(pm25, 2),
                "pm10_filtered": round(pm10, 2),
                "sds011_estado": "OK",
                "sds011_calibracion": "PRUEBA",
                "sds011_muestras": 30,
                "sds011_id": "SIM",
            },
            "ruta": {"estado": "DETENIDO", "motivo_control": "MODO_PRUEBA", "confianza": 0, "desvio_px": 0},
            "motores_visual": {"izquierdo": 0, "derecho": 0, "maximo": 255},
            "yolo": {"activo": False, "requerido": True, "modelo": "", "obstaculo": False},
        }
        sensors = {
            "estado": "OK",
            "uptime_ms": tick * 1000,
            "movimiento": "STOP",
            "motores": {"izquierdo": 0, "derecho": 0, "maximo": 255, "activos": False},
            "sht3x": {"estado": "OK", "temperatura": round(temp, 2), "humedad": round(hum, 2)},
            "sharp": {
                "estado": "LECTURA", "raw": round(sharp_v / 3.3 * 4095, 1),
                "raw_min": 500, "raw_max": 650, "adc_mv": round(sharp_v * 500, 1),
                "vo_v": round(sharp_v, 4), "adc_alto": False,
            },
            "bfs302": {
                "estado": "LECTURA", "raw": round((bfs_v / 2) / 3.3 * 4095, 1),
                "adc_mv": round((bfs_v / 2) * 1000, 1), "aout_v": round(bfs_v, 3), "dout": 1,
            },
            "mg811": {
                "estado": "ESTIMACION_VALIDADA_3_PUNTOS", "gpio": 35,
                "raw": round((mg811_aout / 2) / 1.1 * 4095, 1),
                "adc_mv": round((mg811_aout / 2) * 1000, 2),
                "aout_v": round(mg811_aout, 4), "co2_ppm": round(co2_ppm, 1),
                "calibrado": True, "estable_10min": True,
                "deriva_10min_mv": 0.4, "rango_10min_mv": 2.1,
                "alimentacion_v": 6.0, "linea_base_adc_mv": 146.0,
                "delta_aout_mv": round((mg811_aout - 0.292) * 1000, 2),
                "evento_senal": "SIN_CAMBIO_SIGNIFICATIVO",
                "umbral_evento_aout_mv": 40.0, "listo_para_referencia": True,
                "ppm_validado_tercer_punto": True, "error_validacion_pct": 4.0,
                "metodo_ppm": "interpolacion_logaritmica_dos_referencias_NDIR",
            },
        }

        post("/api/telemetria", telemetry)
        post("/api/sensores/esp32", sensors)
        print(f"PM2.5={pm25:5.1f} | PM10={pm10:5.1f} | CO2={co2_ppm:5.0f} ppm | T={temp:4.1f} C | HR={hum:4.1f}% | Sharp={sharp_v:.3f} V | BFS={bfs_v:.3f} V", flush=True)
        tick += 1
        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSimulación detenida.")
