#!/usr/bin/env python3
"""Puente SDS011 USB/serial -> SALUD AMBIENTAL FastAPI.

Lee PM2.5 y PM10 directamente en Raspberry Pi y publica el snapshot sin
activar camara, YOLO ni motores.
"""
import json
import os
import signal
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sds011_reader import SDS011Reader

URL = os.environ.get(
    "SALUD_AMBIENTAL_SDS011_URL",
    "http://127.0.0.1:5000/api/sensores/sds011",
)
INTERVALO = max(0.3, float(os.environ.get("SDS011_PUBLISH_INTERVAL", "0.5")))
PORT = os.environ.get("SDS011_PORT", "").strip() or None
RUNNING = True


def stop(_signal, _frame):
    global RUNNING
    RUNNING = False


def send_packet(packet):
    body = json.dumps(packet, allow_nan=False).encode("utf-8")
    request = Request(
        URL, data=body, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urlopen(request, timeout=2.0) as response:
        if response.status >= 300:
            raise RuntimeError(f"SALUD AMBIENTAL devolvio HTTP {response.status}")
        return json.load(response)


def fmt(value):
    return "--" if value is None else f"{value:.1f}"


def main():
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    reader = SDS011Reader(port=PORT)
    reader.start()
    print("SALUD AMBIENTAL · Puente SDS011")
    print(f"Puerto : {reader.port}")
    print(f"Destino: {URL}")
    print("PM2.5/PM10: ACTIVOS | Motores: SIN ACCIONES")
    print("Ctrl+C para detener\n")

    try:
        while RUNNING:
            start = time.monotonic()
            packet = reader.snapshot()
            try:
                send_packet(packet)
                print(
                    f"SDS011 {packet.get('sds011_estado')} | "
                    f"PM2.5={fmt(packet.get('pm25'))} ug/m3 | "
                    f"PM10={fmt(packet.get('pm10'))} ug/m3 | "
                    f"RAW={fmt(packet.get('pm25_raw'))}/{fmt(packet.get('pm10_raw'))} | "
                    f"N={packet.get('sds011_muestras', 0)}",
                    flush=True,
                )
            except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as error:
                print(f"No se pudo publicar SDS011: {error}", flush=True)

            wait = max(0, INTERVALO - (time.monotonic() - start))
            if RUNNING and wait:
                time.sleep(wait)
    finally:
        reader.stop()
        print("Puente SDS011 detenido.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
