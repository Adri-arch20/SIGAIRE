"""Pruebas del enlace sensores sin Raspberry ni placa conectadas."""
import csv
import io
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
DB_DIR = tempfile.TemporaryDirectory(prefix="sigaire_sensores_test_")
os.environ["SIGAIRE_DATA_DIR"] = DB_DIR.name
sys.path.insert(0, str(PROJECT / "backend"))

from fastapi.testclient import TestClient
import app.main as api


class Esp32APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(api.app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        DB_DIR.cleanup()

    def test_01_initial_state(self):
        state = self.client.get("/api/estado")
        self.assertEqual(state.status_code, 200)
        self.assertEqual(state.json()["sensores"]["esp32_sensor_estado"], "SIN_CONEXION")

    def test_02_esp32_data(self):
        packet = {
            "estado": "PARCIAL", "uptime_ms": 1000,
            "sht3x": {"estado": "OK", "temperatura": 24.14, "humedad": 57.74},
            "sharp": {"estado": "LECTURA", "raw": 370.0, "raw_min": 360,
                      "raw_max": 385, "adc_mv": 220, "vo_v": 0.44, "adc_alto": False},
            "bfs302": {"estado": "REVISION_ADC", "raw": 0, "adc_mv": 142,
                       "aout_v": 0.284, "dout": 0},
        }
        response = self.client.post("/api/sensores/esp32", json=packet)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["stored"])
        state = self.client.get("/api/estado").json()
        self.assertEqual(state["sensores"]["temperatura"], 24.14)
        self.assertEqual(state["sensores"]["bfs302_dout"], 0)
        self.assertEqual(state["sensores"]["bfs302_estado"], "REVISION_ADC")
        self.assertEqual(state["sensores"]["sharp_vo_v"], 0.44)
        self.assertIsNone(state["sensores"]["pm25"])
        self.assertEqual(self.client.get("/api/sensores/esp32").status_code, 200)
        history = self.client.get("/api/registros").json()["items"]
        self.assertEqual(history[0]["sensores"]["sharp_vo_v"], 0.44)

    def test_03_robot_telemetry_preserved(self):
        response = self.client.post("/api/telemetria", json={
            "robot": "MeteoBot", "estado": "online", "modo": "autonomo",
            "esp32": "conectado", "movimiento": "STOP",
            "sensores": {"pm25": 10.5, "pm10": 20.2},
        })
        self.assertEqual(response.status_code, 200, response.text)
        state = self.client.get("/api/estado").json()
        self.assertAlmostEqual(state["sensores"]["pm25"], 10.5)
        self.assertAlmostEqual(state["sensores"]["sharp_vo_v"], 0.44)
        self.assertEqual(state["modo"], "autonomo")

    def test_04_csv_has_new_columns(self):
        response = self.client.get("/api/registros/export.csv")
        self.assertEqual(response.status_code, 200)
        rows = list(csv.DictReader(io.StringIO(response.text)))
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual(rows[-1]["sharp_vo_v"], "0.44")
        self.assertEqual(rows[-1]["bfs302_dout"], "0")
        self.assertIn("mg811_aout_v", rows[-1])

    def test_05_offline_clears_live_values(self):
        response = self.client.post("/api/sensores/esp32", json={"estado": "SIN_CONEXION"})
        self.assertEqual(response.status_code, 200)
        sensors = self.client.get("/api/estado").json()["sensores"]
        self.assertIsNone(sensors["sharp_vo_v"])
        self.assertIsNone(sensors["temperatura"])
        self.assertEqual(sensors["esp32_sensor_estado"], "SIN_CONEXION")

    def test_06_expired_readings(self):
        packet = {"estado": "OK", "sht3x": {"estado": "OK", "temperatura": 23, "humedad": 55}}
        self.client.post("/api/sensores/esp32", json=packet)
        api._sensor_cache_at = time.monotonic() - api.ESP32_SENSOR_TTL_SECONDS - 1
        self.assertIsNone(self.client.get("/api/estado").json()["sensores"]["temperatura"])

    def test_07_invalid_dout(self):
        response = self.client.post("/api/sensores/esp32", json={"bfs302": {"dout": 5}})
        self.assertEqual(response.status_code, 422)

    def test_08_movement_shown_from_actual_esp32_pwm(self):
        packet = {
            "estado": "OK", "movimiento": "IZQUIERDA",
            "motores": {"izquierdo": 120, "derecho": 145, "maximo": 255, "activos": True},
            "sht3x": {"estado": "OK", "temperatura": 24.0, "humedad": 57.0},
            "sharp": {"estado": "LECTURA", "raw": 365, "adc_mv": 215, "vo_v": 0.43},
            "bfs302": {"estado": "REVISION_ADC", "raw": 0, "adc_mv": 142, "aout_v": 0.284, "dout": 0},
        }
        response = self.client.post("/api/sensores/esp32", json=packet)
        self.assertEqual(response.status_code, 200, response.text)
        state = self.client.get("/api/estado").json()
        self.assertEqual(state["movimiento"], "IZQUIERDA")
        self.assertEqual(state["motores_visual"]["izquierdo"], 120)
        self.assertEqual(state["motores_visual"]["derecho"], 145)
        self.assertEqual(state["sensores"]["esp32_movimiento"], "IZQUIERDA")
        self.assertTrue(state["sensores"]["esp32_motores_activos"])

    def test_09_invalid_motor_pwm(self):
        response = self.client.post(
            "/api/sensores/esp32",
            json={"estado": "OK", "motores": {"izquierdo": 500, "derecho": 0}},
        )
        self.assertEqual(response.status_code, 422)

    def test_10_movement_stops_when_esp32_reports_stop(self):
        response = self.client.post("/api/sensores/esp32", json={
            "estado": "OK", "movimiento": "STOP",
            "motores": {"izquierdo": 0, "derecho": 0, "maximo": 255, "activos": False},
        })
        self.assertEqual(response.status_code, 200)
        state = self.client.get("/api/estado").json()
        self.assertEqual(state["movimiento"], "STOP")
        self.assertEqual(state["motores_visual"]["izquierdo"], 0)

    def test_11_expired_movement_not_reported_as_current(self):
        self.client.post("/api/sensores/esp32", json={
            "estado": "OK", "movimiento": "AVANZAR",
            "motores": {"izquierdo": 150, "derecho": 150, "activos": True},
        })
        api._sensor_cache_at = time.monotonic() - api.ESP32_SENSOR_TTL_SECONDS - 1
        api._last_robot_at = time.monotonic() - api.ROBOT_LIVE_TTL_SECONDS - 1
        state = self.client.get("/api/estado").json()
        self.assertEqual(state["movimiento"], "STOP")
        self.assertEqual(state["motores_visual"]["izquierdo"], 0)
        self.assertEqual(state["esp32"], "desconectado")


    def test_12_sds011_independent_bridge(self):
        packet = {
            "pm25": 12.4, "pm10": 24.8,
            "pm25_raw": 13.0, "pm10_raw": 25.2,
            "pm25_filtered": 12.4, "pm10_filtered": 24.8,
            "sds011_estado": "OK", "sds011_muestras": 15,
            "sds011_puerto": "/dev/ttyUSB0",
        }
        response = self.client.post("/api/sensores/sds011", json=packet)
        self.assertEqual(response.status_code, 200, response.text)
        state = self.client.get("/api/estado").json()
        self.assertAlmostEqual(state["sensores"]["pm25"], 12.4)
        self.assertAlmostEqual(state["sensores"]["pm10"], 24.8)
        self.assertEqual(state["sensores"]["sds011_estado"], "OK")
        self.assertEqual(self.client.get("/api/sensores/sds011").status_code, 200)

    def test_13_sds011_and_esp32_are_merged(self):
        self.client.post("/api/sensores/esp32", json={
            "estado": "OK",
            "sht3x": {"estado": "OK", "temperatura": 22.5, "humedad": 51.0},
        })
        state = self.client.get("/api/estado").json()
        self.assertAlmostEqual(state["sensores"]["pm25"], 12.4)
        self.assertAlmostEqual(state["sensores"]["temperatura"], 22.5)

    def test_14_mg811_calibrated_co2_is_merged(self):
        packet = {
            "estado": "OK",
            "sht3x": {"estado": "OK", "temperatura": 23.4, "humedad": 50.1},
            "sharp": {"estado": "LECTURA", "raw": 360, "adc_mv": 220, "vo_v": 0.44},
            "bfs302": {"estado": "LECTURA", "raw": 100, "adc_mv": 150, "aout_v": 0.30, "dout": 1},
            "mg811": {
                "estado": "ESTIMACION_VALIDADA_3_PUNTOS", "gpio": 35,
                "raw": 180.0, "adc_mv": 145.0, "aout_v": 0.2900,
                "co2_ppm": 612.5, "calibrado": True, "estable_10min": True,
                "deriva_10min_mv": 0.5, "rango_10min_mv": 2.0,
                "alimentacion_v": 6.0, "linea_base_adc_mv": 146.0,
                "delta_aout_mv": -2.0, "evento_senal": "SIN_CAMBIO_SIGNIFICATIVO",
                "umbral_evento_aout_mv": 40.0, "listo_para_referencia": True,
                "ppm_validado_tercer_punto": True, "error_validacion_pct": 4.2,
                "metodo_ppm": "interpolacion_logaritmica_dos_referencias_NDIR"
            },
        }
        response = self.client.post("/api/sensores/esp32", json=packet)
        self.assertEqual(response.status_code, 200, response.text)
        sensors = self.client.get("/api/estado").json()["sensores"]
        self.assertAlmostEqual(sensors["co2"], 612.5)
        self.assertAlmostEqual(sensors["mg811_aout_v"], 0.29)
        self.assertEqual(sensors["mg811_estado"], "ESTIMACION_VALIDADA_3_PUNTOS")
        self.assertTrue(sensors["mg811_calibrado"])
        history = self.client.get("/api/registros").json()["items"]
        self.assertAlmostEqual(history[0]["sensores"]["co2"], 612.5)
        self.assertAlmostEqual(history[0]["sensores"]["mg811_aout_v"], 0.29)

    def test_15_mg811_uncalibrated_keeps_voltage_without_fake_ppm(self):
        response = self.client.post("/api/sensores/esp32", json={
            "estado": "PARCIAL",
            "mg811": {
                "estado": "SIN_CALIBRAR", "gpio": 35, "raw": 178.0,
                "adc_mv": 143.6, "aout_v": 0.2872, "co2_ppm": None,
                "calibrado": False, "estable_10min": False,
                "evento_senal": "SIN_BASE", "alimentacion_v": 6.0
            }
        })
        self.assertEqual(response.status_code, 200, response.text)
        sensors = self.client.get("/api/estado").json()["sensores"]
        self.assertIsNone(sensors["co2"])
        self.assertAlmostEqual(sensors["mg811_aout_v"], 0.2872)
        self.assertEqual(sensors["mg811_estado"], "SIN_CALIBRAR")


if __name__ == "__main__":
    unittest.main(verbosity=2)
