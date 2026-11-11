#!/usr/bin/env python3

from collections import deque
from glob import glob
from pathlib import Path
import json
import math
import os
import threading
import time

import numpy as np
import serial


class SDS011Reader:
    """
    Lector robusto para Nova Fitness SDS011.

    Flujo de procesamiento:
      1. Valida la trama UART (AA C0 ... checksum ... AB).
      2. Rechaza valores digitales fuera de rango.
      3. Aplica ventana movil.
      4. Detecta outliers con mediana + MAD.
      5. Calcula media recortada.
      6. Suaviza con EMA para conservar respuesta en tiempo real.
      7. Aplica calibracion lineal configurable:
           PM_final = slope * PM_filtrado + intercept

    IMPORTANTE:
    El filtrado mejora estabilidad/repetibilidad, pero una calibracion
    metrologica real requiere comparar este sensor contra un instrumento
    de referencia en el mismo lugar y periodo.
    """

    def __init__(
        self,
        port=None,
        calibration_path=None,
    ):
        self.base_dir = Path(__file__).resolve().parent
        self.calibration_path = Path(
            calibration_path
            or os.getenv(
                "SDS011_CALIBRATION",
                str(self.base_dir / "sds011_calibration.json"),
            )
        )

        config = self._load_config()
        filter_cfg = config.get("filter", {})

        self.port = port or self.detect_port()

        self.warmup_seconds = int(
            filter_cfg.get("warmup_seconds", 60)
        )

        self.window_size = max(
            5,
            int(filter_cfg.get("window_size", 15)),
        )

        self.ema_alpha = float(
            filter_cfg.get("ema_alpha", 0.35)
        )

        self.mad_sigma = float(
            filter_cfg.get("mad_sigma", 3.5)
        )

        self.min_valid_samples = max(
            3,
            int(filter_cfg.get("min_valid_samples", 5)),
        )

        self.stale_seconds = float(
            filter_cfg.get("stale_seconds", 5)
        )

        self.pm25_slope = float(
            config.get("pm25", {}).get("slope", 1.0)
        )
        self.pm25_intercept = float(
            config.get("pm25", {}).get("intercept", 0.0)
        )

        self.pm10_slope = float(
            config.get("pm10", {}).get("slope", 1.0)
        )
        self.pm10_intercept = float(
            config.get("pm10", {}).get("intercept", 0.0)
        )

        self._factory_only = (
            math.isclose(self.pm25_slope, 1.0, abs_tol=1e-9)
            and math.isclose(self.pm25_intercept, 0.0, abs_tol=1e-9)
            and math.isclose(self.pm10_slope, 1.0, abs_tol=1e-9)
            and math.isclose(self.pm10_intercept, 0.0, abs_tol=1e-9)
        )

        self._pm25 = deque(maxlen=self.window_size)
        self._pm10 = deque(maxlen=self.window_size)

        self._pm25_ema = None
        self._pm10_ema = None

        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._serial = None

        self._started_at = None
        self._last_valid = None

        self._state = {
            "pm25": None,
            "pm10": None,

            "pm25_raw": None,
            "pm10_raw": None,

            "pm25_filtered": None,
            "pm10_filtered": None,

            "pm25_std": None,
            "pm10_std": None,

            "pm25_min": None,
            "pm25_max": None,
            "pm10_min": None,
            "pm10_max": None,

            "sds011_estado": "SIN_DATOS",
            "sds011_calibracion": (
                "FABRICA"
                if self._factory_only
                else "REFERENCIA"
            ),
            "sds011_muestras": 0,
            "sds011_id": "",
            "sds011_puerto": self.port or "",
            "sds011_tramas_invalidas": 0,
            "sds011_outliers": 0,
        }

    def _load_config(self):
        try:
            return json.loads(
                self.calibration_path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            return {
                "pm25": {
                    "slope": 1.0,
                    "intercept": 0.0,
                },
                "pm10": {
                    "slope": 1.0,
                    "intercept": 0.0,
                },
                "filter": {},
            }

    @staticmethod
    def detect_port():
        env_port = os.getenv("SDS011_PORT")

        if env_port:
            return env_port

        by_id = sorted(
            glob("/dev/serial/by-id/*")
        )

        # Si solo hay un adaptador USB-serial, by-id es preferible
        # porque su ruta permanece estable aunque cambie ttyUSB0/1.
        if len(by_id) == 1:
            return by_id[0]

        tty_usb = sorted(
            glob("/dev/ttyUSB*")
        )

        if tty_usb:
            return tty_usb[0]

        return "/dev/ttyUSB0"

    def _set_status(self, status):
        with self._lock:
            self._state["sds011_estado"] = status

    def _invalid_frame(self):
        with self._lock:
            self._state["sds011_tramas_invalidas"] += 1

    def _open_serial(self):
        self._serial = serial.Serial(
            port=self.port,
            baudrate=9600,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=2,
        )

        self._serial.reset_input_buffer()

    def _read_frame(self):
        while self._running:
            first = self._serial.read(1)

            if not first:
                return None

            if first[0] != 0xAA:
                continue

            second = self._serial.read(1)

            if (
                not second
                or second[0] != 0xC0
            ):
                continue

            rest = self._serial.read(8)

            if len(rest) != 8:
                return None

            pm25_low = rest[0]
            pm25_high = rest[1]
            pm10_low = rest[2]
            pm10_high = rest[3]
            id1 = rest[4]
            id2 = rest[5]
            checksum_received = rest[6]
            tail = rest[7]

            if tail != 0xAB:
                self._invalid_frame()
                continue

            checksum = (
                pm25_low
                + pm25_high
                + pm10_low
                + pm10_high
                + id1
                + id2
            ) & 0xFF

            if checksum != checksum_received:
                self._invalid_frame()
                continue

            pm25 = (
                (pm25_high * 256)
                + pm25_low
            ) / 10.0

            pm10 = (
                (pm10_high * 256)
                + pm10_low
            ) / 10.0

            if not (
                0.0 <= pm25 <= 999.9
                and 0.0 <= pm10 <= 999.9
            ):
                self._invalid_frame()
                continue

            return {
                "pm25": pm25,
                "pm10": pm10,
                "id": f"{id2:02X}{id1:02X}",
            }

        return None

    def _robust_window(self, values):
        arr = np.asarray(
            list(values),
            dtype=np.float64,
        )

        if arr.size == 0:
            return {
                "value": None,
                "std": None,
                "min": None,
                "max": None,
                "outliers": 0,
                "n": 0,
            }

        median = float(
            np.median(arr)
        )

        deviations = np.abs(
            arr - median
        )

        mad = float(
            np.median(deviations)
        )

        if mad > 0:
            robust_sigma = 1.4826 * mad

            threshold = max(
                1.0,
                self.mad_sigma
                * robust_sigma,
            )

            keep = (
                deviations <= threshold
            )

            clean = arr[keep]
            outliers = int(
                arr.size - clean.size
            )

            if clean.size < self.min_valid_samples:
                clean = arr
                outliers = 0

        else:
            clean = arr
            outliers = 0

        clean = np.sort(clean)

        # Media recortada 10% cuando la ventana ya es suficiente.
        if clean.size >= 10:
            trim = max(
                1,
                int(clean.size * 0.10),
            )

            if clean.size - (2 * trim) >= self.min_valid_samples:
                clean = clean[trim:-trim]

        return {
            "value": float(
                np.mean(clean)
            ),
            "std": float(
                np.std(clean)
            ),
            "min": float(
                np.min(clean)
            ),
            "max": float(
                np.max(clean)
            ),
            "outliers": outliers,
            "n": int(clean.size),
        }

    def _ema(self, previous, value):
        if value is None:
            return previous

        if previous is None:
            return value

        alpha = min(
            1.0,
            max(
                0.01,
                self.ema_alpha,
            ),
        )

        return (
            alpha * value
            + (1.0 - alpha) * previous
        )

    @staticmethod
    def _calibrate(value, slope, intercept):
        if value is None:
            return None

        return max(
            0.0,
            (slope * value)
            + intercept,
        )

    def _process_frame(self, frame):
        now = time.monotonic()
        self._last_valid = now

        self._pm25.append(
            frame["pm25"]
        )
        self._pm10.append(
            frame["pm10"]
        )

        pm25_stats = self._robust_window(
            self._pm25
        )

        pm10_stats = self._robust_window(
            self._pm10
        )

        self._pm25_ema = self._ema(
            self._pm25_ema,
            pm25_stats["value"],
        )

        self._pm10_ema = self._ema(
            self._pm10_ema,
            pm10_stats["value"],
        )

        pm25_final = self._calibrate(
            self._pm25_ema,
            self.pm25_slope,
            self.pm25_intercept,
        )

        pm10_final = self._calibrate(
            self._pm10_ema,
            self.pm10_slope,
            self.pm10_intercept,
        )

        elapsed = (
            now - self._started_at
        )

        enough_samples = (
            len(self._pm25)
            >= self.min_valid_samples
            and
            len(self._pm10)
            >= self.min_valid_samples
        )

        if elapsed < self.warmup_seconds:
            status = "CALENTANDO"
            published_pm25 = None
            published_pm10 = None

        elif not enough_samples:
            status = "ESTABILIZANDO"
            published_pm25 = None
            published_pm10 = None

        else:
            status = "OK"
            published_pm25 = pm25_final
            published_pm10 = pm10_final

        with self._lock:
            self._state.update(
                {
                    "pm25": published_pm25,
                    "pm10": published_pm10,

                    "pm25_raw": frame["pm25"],
                    "pm10_raw": frame["pm10"],

                    "pm25_filtered": self._pm25_ema,
                    "pm10_filtered": self._pm10_ema,

                    "pm25_std": pm25_stats["std"],
                    "pm10_std": pm10_stats["std"],

                    "pm25_min": pm25_stats["min"],
                    "pm25_max": pm25_stats["max"],
                    "pm10_min": pm10_stats["min"],
                    "pm10_max": pm10_stats["max"],

                    "sds011_estado": status,
                    "sds011_calibracion": (
                        "FABRICA"
                        if self._factory_only
                        else "REFERENCIA"
                    ),
                    "sds011_muestras": min(
                        len(self._pm25),
                        len(self._pm10),
                    ),
                    "sds011_id": frame["id"],
                    "sds011_puerto": self.port,
                    "sds011_outliers": (
                        pm25_stats["outliers"]
                        + pm10_stats["outliers"]
                    ),
                }
            )

    def _loop(self):
        self._started_at = time.monotonic()

        while self._running:
            try:
                if (
                    self._serial is None
                    or not self._serial.is_open
                ):
                    self._set_status(
                        "ABRIENDO_PUERTO"
                    )

                    self._open_serial()

                    self._set_status(
                        "CALENTANDO"
                    )

                frame = self._read_frame()

                if frame is not None:
                    self._process_frame(
                        frame
                    )
                    continue

                now = time.monotonic()

                if (
                    self._last_valid is not None
                    and
                    now - self._last_valid
                    > self.stale_seconds
                ):
                    self._set_status(
                        "SIN_DATOS"
                    )

            except (
                serial.SerialException,
                OSError,
            ):
                self._set_status(
                    "ERROR_PUERTO"
                )

                try:
                    if self._serial is not None:
                        self._serial.close()
                except Exception:
                    pass

                self._serial = None
                time.sleep(2)

            except Exception:
                self._set_status(
                    "ERROR"
                )
                time.sleep(1)

    def start(self):
        if self._running:
            return

        self._running = True

        self._thread = threading.Thread(
            target=self._loop,
            name="SDS011Reader",
            daemon=True,
        )

        self._thread.start()

    def snapshot(self):
        with self._lock:
            state = dict(
                self._state
            )

        if self._started_at is not None:
            elapsed = (
                time.monotonic()
                - self._started_at
            )

            state[
                "sds011_calentamiento_restante"
            ] = max(
                0,
                int(
                    self.warmup_seconds
                    - elapsed
                ),
            )

        else:
            state[
                "sds011_calentamiento_restante"
            ] = self.warmup_seconds

        if self._last_valid is not None:
            state[
                "sds011_edad_lectura_s"
            ] = round(
                time.monotonic()
                - self._last_valid,
                2,
            )

        else:
            state[
                "sds011_edad_lectura_s"
            ] = None

        state["sds011_pm25_slope"] = self.pm25_slope
        state["sds011_pm25_intercept"] = self.pm25_intercept
        state["sds011_pm10_slope"] = self.pm10_slope
        state["sds011_pm10_intercept"] = self.pm10_intercept

        return state

    def stop(self):
        self._running = False

        try:
            if self._serial is not None:
                self._serial.close()
        except Exception:
            pass

        if self._thread is not None:
            self._thread.join(
                timeout=2
            )


def main():
    reader = SDS011Reader()
    reader.start()

    print()
    print("======================================================")
    print(" SDS011 - METEOBOT / LECTURA ROBUSTA + CALIBRACION")
    print("======================================================")
    print(f"Puerto: {reader.port}")
    print(f"Calibracion: {reader.calibration_path}")
    print(
        "Durante el calentamiento el sensor se lee, "
        "pero PM final permanece sin publicar."
    )
    print("Ctrl+C para finalizar.")
    print()

    try:
        while True:
            data = reader.snapshot()

            def fmt(value):
                if value is None:
                    return "--"
                return f"{value:.1f}"

            print(
                f"\rEstado={data['sds011_estado']:14} | "
                f"PM2.5 raw={fmt(data['pm25_raw']):>6} "
                f"fil={fmt(data['pm25_filtered']):>6} "
                f"final={fmt(data['pm25']):>6} | "
                f"PM10 raw={fmt(data['pm10_raw']):>6} "
                f"fil={fmt(data['pm10_filtered']):>6} "
                f"final={fmt(data['pm10']):>6} | "
                f"N={data['sds011_muestras']:2} | "
                f"OUT={data['sds011_outliers']:2}",
                end="",
                flush=True,
            )

            time.sleep(0.5)

    except KeyboardInterrupt:
        print()

    finally:
        reader.stop()
        print("SDS011 detenido.")


if __name__ == "__main__":
    main()
