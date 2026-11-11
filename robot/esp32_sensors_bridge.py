#!/usr/bin/env python3
"""Puente independiente: ESP32 GET /sensores -> FastAPI POST /api/sensores/esp32.

Solo lee sensores; nunca envia ordenes de movimiento. Compatible con Python 3
sin paquetes externos, incluso cuando YOLO/camara no estan en ejecucion.
"""
import json
import os
import signal
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ESP32_IP = os.environ.get("METEOBOT_ESP32_IP", "192.168.137.200").strip()
ESP32_URL = os.environ.get("METEOBOT_SENSORS_ESP32_URL", f"http://{ESP32_IP}/sensores")
SIGAIRE_URL = os.environ.get("SIGAIRE_SENSORS_URL", "http://127.0.0.1:5000/api/sensores/esp32")
INTERVALO = max(0.3, float(os.environ.get("METEOBOT_SENSOR_INTERVAL", "0.5")))
TIMEOUT = max(0.2, float(os.environ.get("METEOBOT_SENSOR_TIMEOUT", "1.0")))
RUNNING = True


def stop(_signal, _frame):
    global RUNNING
    RUNNING = False


def get_packet():
    request = Request(ESP32_URL, headers={"Accept": "application/json"})
    with urlopen(request, timeout=TIMEOUT) as response:
        data = json.load(response)
    if not isinstance(data, dict):
        raise ValueError("JSON del ESP32 no es un objeto")
    if data.get("origen") != "ESP32":
        raise ValueError("Firmware incompatible: falta origen=ESP32")
    for name in ("sht3x", "sharp", "bfs302"):
        if not isinstance(data.get(name), dict):
            raise ValueError(f"Firmware incompatible: falta campo {name}")
    # V7.2 acepta firmware anterior mientras se actualiza la placa; si MG811
    # todavia no existe, se publica explicitamente como SIN_DATOS.
    if not isinstance(data.get("mg811"), dict):
        data["mg811"] = {"estado": "SIN_DATOS", "co2_ppm": None, "calibrado": False}
    return data


def send_packet(packet):
    body = json.dumps(packet, allow_nan=False).encode("utf-8")
    request = Request(
        SIGAIRE_URL,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urlopen(request, timeout=TIMEOUT) as response:
        if response.status >= 300:
            raise RuntimeError(f"SALUD AMBIENTAL devolvió HTTP {response.status}")
        return json.load(response)


def main():
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    print("SALUD AMBIENTAL · Puente de sensores ESP32")
    print(f"Origen : {ESP32_URL}")
    print(f"Destino: {SIGAIRE_URL}")
    print("Motor : SIN ACCIONES (solo lecturas)")
    print("Ctrl+C para detener\n")

    while RUNNING:
        inicio = time.monotonic()
        try:
            packet = get_packet()
            resumen = packet.get("estado", "SIN_DATOS")
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as error:
            resumen = "SIN_CONEXION"
            packet = {"estado": "SIN_CONEXION"}
            print(f"ESP32 no accesible: {error}", flush=True)

        try:
            send_packet(packet)
            if resumen != "SIN_CONEXION":
                sht = packet.get("sht3x", {})
                sharp = packet.get("sharp", {})
                bfs = packet.get("bfs302", {})
                mg811 = packet.get("mg811", {})
                ppm = mg811.get("co2_ppm")
                co2_texto = f"{ppm} ppm" if ppm is not None else f"{mg811.get('aout_v')} V AOUT / {mg811.get('estado', 'SIN_DATOS')}"
                print(
                    f"ESP32 {resumen} | T={sht.get('temperatura')} °C "
                    f"HR={sht.get('humedad')} % | Sharp={sharp.get('vo_v')} V "
                    f"BFS={bfs.get('aout_v')} V / DOUT={bfs.get('dout')} | "
                    f"MG811={co2_texto}",
                    flush=True,
                )
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as error:
            print(f"No se pudo publicar en SALUD AMBIENTAL: {error}", flush=True)

        espera = max(0, INTERVALO - (time.monotonic() - inicio))
        if RUNNING and espera:
            time.sleep(espera)

    print("Puente detenido.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
