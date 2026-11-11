import asyncio
import copy
import json
import os
import time
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .database import (
    delete_all_records,
    delete_record,
    export_csv_text,
    init_db,
    insert_telemetry,
    latest_record,
    list_records,
    stats,
)
from .schemas import Esp32SensorsIn, SDS011SensorsIn, TelemetryIn


STORE_INTERVAL_SECONDS = float(
    os.getenv("SIGAIRE_STORE_INTERVAL", os.getenv("SINGARE_STORE_INTERVAL", "1.0"))
)

_last_store_time = 0.0
_last_signature: tuple[Any, ...] | None = None

# Snapshot en memoria; no se reutilizan valores antiguos como si fueran actuales.
ESP32_SENSOR_TTL_SECONDS = max(3.0, float(os.getenv("SIGAIRE_SENSOR_TTL", "8")))
ROBOT_LIVE_TTL_SECONDS = 4.0
SDS011_SENSOR_TTL_SECONDS = max(3.0, float(os.getenv("SALUD_AMBIENTAL_SDS011_TTL", "8")))
_sds_cache: dict[str, Any] | None = None
_sds_cache_at = 0.0
_sensor_cache: dict[str, Any] | None = None
_sensor_cache_at = 0.0
_last_robot: dict[str, Any] | None = None
_last_robot_at = 0.0
_last_live: dict[str, Any] | None = None

_SENSOR_VALUES = (
    "temperatura", "humedad", "sharp_raw", "sharp_raw_min", "sharp_raw_max",
    "sharp_adc_mv", "sharp_vo_v", "sharp_adc_alto",
    "bfs302_raw", "bfs302_adc_mv", "bfs302_aout_v", "bfs302_dout",
    "co2", "mg811_raw", "mg811_adc_mv", "mg811_aout_v",
    "mg811_calibrado", "mg811_estable_10min", "mg811_deriva_10min_mv",
    "mg811_rango_10min_mv", "mg811_alimentacion_v", "mg811_linea_base_adc_mv",
    "mg811_delta_aout_mv", "mg811_evento_senal", "mg811_umbral_evento_aout_mv",
    "mg811_listo_para_referencia", "mg811_ppm_validado_tercer_punto",
    "mg811_error_validacion_pct", "mg811_metodo_ppm",
    "esp32_movimiento", "esp32_motor_izquierdo", "esp32_motor_derecho",
    "esp32_motores_activos",
)


def _sensor_overlay() -> dict[str, Any]:
    active = (
        _sensor_cache is not None
        and time.monotonic() - _sensor_cache_at <= ESP32_SENSOR_TTL_SECONDS
    )
    if not active:
        return {
            **{key: None for key in _SENSOR_VALUES},
            "esp32_sensor_estado": "SIN_CONEXION",
            "esp32_sensor_edad_s": None,
            "sht3x_estado": "SIN_DATOS",
            "sharp_estado": "SIN_DATOS",
            "bfs302_estado": "SIN_DATOS",
            "mg811_estado": "SIN_DATOS",
        }

    packet = _sensor_cache or {}
    sht = packet.get("sht3x") or {}
    sharp = packet.get("sharp") or {}
    bfs = packet.get("bfs302") or {}
    mg811 = packet.get("mg811") or {}
    motors = packet.get("motores") or {}
    ok = packet.get("estado") not in ("SIN_CONEXION", "SIN_DATOS")
    return {
        "esp32_sensor_estado": packet.get("estado", "SIN_DATOS"),
        "esp32_sensor_edad_s": round(time.monotonic() - _sensor_cache_at, 2),
        "sht3x_estado": sht.get("estado", "SIN_DATOS") if ok else "SIN_DATOS",
        "temperatura": sht.get("temperatura") if ok else None,
        "humedad": sht.get("humedad") if ok else None,
        "sharp_estado": sharp.get("estado", "SIN_DATOS") if ok else "SIN_DATOS",
        "sharp_raw": sharp.get("raw") if ok else None,
        "sharp_raw_min": sharp.get("raw_min") if ok else None,
        "sharp_raw_max": sharp.get("raw_max") if ok else None,
        "sharp_adc_mv": sharp.get("adc_mv") if ok else None,
        "sharp_vo_v": sharp.get("vo_v") if ok else None,
        "sharp_adc_alto": sharp.get("adc_alto") if ok else None,
        "bfs302_estado": bfs.get("estado", "SIN_DATOS") if ok else "SIN_DATOS",
        "bfs302_raw": bfs.get("raw") if ok else None,
        "bfs302_adc_mv": bfs.get("adc_mv") if ok else None,
        "bfs302_aout_v": bfs.get("aout_v") if ok else None,
        "bfs302_dout": bfs.get("dout") if ok else None,
        "mg811_estado": mg811.get("estado", "SIN_DATOS") if ok else "SIN_DATOS",
        # CO2 solo se publica como ppm si el propio firmware entrega una estimacion
        # calibrada/valida. El voltaje del MG811 siempre queda disponible aparte.
        "co2": mg811.get("co2_ppm") if ok else None,
        "mg811_raw": mg811.get("raw") if ok else None,
        "mg811_adc_mv": mg811.get("adc_mv") if ok else None,
        "mg811_aout_v": mg811.get("aout_v") if ok else None,
        "mg811_calibrado": mg811.get("calibrado") if ok else None,
        "mg811_estable_10min": mg811.get("estable_10min") if ok else None,
        "mg811_deriva_10min_mv": mg811.get("deriva_10min_mv") if ok else None,
        "mg811_rango_10min_mv": mg811.get("rango_10min_mv") if ok else None,
        "mg811_alimentacion_v": mg811.get("alimentacion_v") if ok else None,
        "mg811_linea_base_adc_mv": mg811.get("linea_base_adc_mv") if ok else None,
        "mg811_delta_aout_mv": mg811.get("delta_aout_mv") if ok else None,
        "mg811_evento_senal": mg811.get("evento_senal") if ok else None,
        "mg811_umbral_evento_aout_mv": mg811.get("umbral_evento_aout_mv") if ok else None,
        "mg811_listo_para_referencia": mg811.get("listo_para_referencia") if ok else None,
        "mg811_ppm_validado_tercer_punto": mg811.get("ppm_validado_tercer_punto") if ok else None,
        "mg811_error_validacion_pct": mg811.get("error_validacion_pct") if ok else None,
        "mg811_metodo_ppm": mg811.get("metodo_ppm") if ok else None,
        "esp32_movimiento": packet.get("movimiento") if ok else None,
        "esp32_motor_izquierdo": motors.get("izquierdo") if ok else None,
        "esp32_motor_derecho": motors.get("derecho") if ok else None,
        "esp32_motores_activos": motors.get("activos") if ok else None,
    }


_SDS011_VALUES = (
    "pm25", "pm10", "pm25_raw", "pm10_raw",
    "pm25_filtered", "pm10_filtered", "pm25_std", "pm10_std",
    "pm25_min", "pm25_max", "pm10_min", "pm10_max",
    "sds011_calibracion", "sds011_muestras", "sds011_id",
    "sds011_puerto", "sds011_tramas_invalidas", "sds011_outliers",
    "sds011_calentamiento_restante", "sds011_edad_lectura_s",
)


def _sds011_overlay() -> dict[str, Any]:
    active = (
        _sds_cache is not None
        and time.monotonic() - _sds_cache_at <= SDS011_SENSOR_TTL_SECONDS
    )
    if not active:
        return {
            "_active": False,
            **{key: None for key in _SDS011_VALUES},
            "sds011_estado": "SIN_CONEXION",
        }

    packet = _sds_cache or {}
    return {
        "_active": True,
        **{key: packet.get(key) for key in _SDS011_VALUES},
        "sds011_estado": packet.get("sds011_estado", "SIN_DATOS"),
    }


def _merge_sensors(data: dict[str, Any]) -> dict[str, Any]:
    data = copy.deepcopy(data)
    sensor_data = data.setdefault("sensores", {})

    # SDS011 puede funcionar independientemente del proceso YOLO/autonomo.
    # Si su puente esta activo, su lectura directa tiene prioridad. Si no esta
    # activo, se conserva la lectura SDS011 que pudiera venir del robot autonomo.
    sds_overlay = _sds011_overlay()
    sds_active = bool(sds_overlay.pop("_active", False))
    if sds_active:
        sensor_data.update(sds_overlay)
    elif (
        data.get("modo") == "monitoreo_sensores"
        or _last_robot is None
        or time.monotonic() - _last_robot_at > ROBOT_LIVE_TTL_SECONDS
    ):
        sensor_data.update(sds_overlay)

    overlay = _sensor_overlay()
    sensor_data.update(overlay)
    # El ESP32 informa el PWM aplicado. Prioridad sobre los valores
    # ordenados por YOLO, que pueden diferir tras un STOP por watchdog.
    if overlay["esp32_movimiento"] is not None:
        data["movimiento"] = overlay["esp32_movimiento"]
        data["esp32"] = "conectado"
        if overlay["esp32_motor_izquierdo"] is not None and overlay["esp32_motor_derecho"] is not None:
            data["motores_visual"] = {
                "izquierdo": overlay["esp32_motor_izquierdo"],
                "derecho": overlay["esp32_motor_derecho"],
                "maximo": 255,
            }
    elif (
        data.get("modo") == "monitoreo_sensores"
        or _last_robot is None
        or time.monotonic() - _last_robot_at > ROBOT_LIVE_TTL_SECONDS
    ):
        # Si desaparece el puente y/o el proceso de navegacion, no mostrar PWM antiguos
        # como si los motores continuaran moviendose.
        data["movimiento"] = "STOP"
        data["esp32"] = "desconectado"
        data["motores_visual"] = {"izquierdo": 0, "derecho": 0, "maximo": 255}
    return data


def _live_state() -> dict[str, Any]:
    original = _last_live if _last_live is not None else latest_record()
    if original is None:
        original = TelemetryIn().model_dump()
        original["ruta"] = {"estado": "SIN_DATOS", "motivo_control": "ESPERANDO_TELEMETRIA"}
        original["motores_visual"] = {"izquierdo": 0, "derecho": 0, "maximo": 255}
        original["yolo"] = {"activo": False, "requerido": True, "modelo": "", "obstaculo": False}
    return _merge_sensors(original)


async def _publish(data: dict[str, Any]) -> dict[str, Any]:
    global _last_store_time, _last_signature, _last_live

    data = _merge_sensors(data)
    data["timestamp"] = datetime.now().astimezone().isoformat(timespec="milliseconds")

    signature = (
        data.get("movimiento"), data.get("gesto"), data.get("esp32"),
        data.get("estado"), (data.get("vision") or {}).get("objeto"),
        (data.get("sensores") or {}).get("esp32_sensor_estado"),
        (data.get("sensores") or {}).get("sds011_estado"),
        (data.get("sensores") or {}).get("mg811_estado"),
    )
    now = time.monotonic()
    should_store = (_last_signature != signature or now - _last_store_time >= STORE_INTERVAL_SECONDS)
    record = None
    if should_store:
        record = insert_telemetry(data)
        _last_store_time = now
        _last_signature = signature

    live_payload = {**data, "stored": should_store, "id": record.get("id") if record else None}
    _last_live = data
    await manager.broadcast(live_payload)
    return {"ok": True, "stored": should_store, "id": record.get("id") if record else None}


class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []

        for websocket in self.active:
            try:
                await websocket.send_json(payload)
            except Exception:
                dead.append(websocket)

        for websocket in dead:
            self.disconnect(websocket)


manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="SALUD AMBIENTAL API",
    version="7.2.0",
    description="Backend local de SALUD AMBIENTAL para telemetría, sensores y navegación autónoma de MeteoBot.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/salud")
async def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "SALUD AMBIENTAL",
        "version": "7.2.0",
        "websocket_clients": len(manager.active),
        "store_interval_seconds": STORE_INTERVAL_SECONDS,
    }


@app.post("/api/telemetria")
async def telemetry(payload: TelemetryIn) -> dict[str, Any]:
    global _last_robot, _last_robot_at
    data = payload.model_dump()
    _last_robot = data
    _last_robot_at = time.monotonic()
    return await _publish(data)


@app.post("/api/sensores/esp32")
async def receive_esp32_sensors(payload: Esp32SensorsIn) -> dict[str, Any]:
    """La Raspberry publica las medidas ESP32 sin depender de la camara/YOLO."""
    global _sensor_cache, _sensor_cache_at

    _sensor_cache = payload.model_dump()
    _sensor_cache_at = time.monotonic()

    if _last_robot is not None and time.monotonic() - _last_robot_at <= ROBOT_LIVE_TTL_SECONDS:
        data = copy.deepcopy(_last_robot)
    else:
        data = TelemetryIn().model_dump()
        data["modo"] = "monitoreo_sensores"
        data["esp32"] = "conectado" if payload.estado != "SIN_CONEXION" else "desconectado"

    return await _publish(data)


@app.post("/api/sensores/sds011")
async def receive_sds011_sensors(payload: SDS011SensorsIn) -> dict[str, Any]:
    """Publica PM2.5/PM10 del SDS011 sin requerir camara, YOLO ni motores."""
    global _sds_cache, _sds_cache_at

    _sds_cache = payload.model_dump()
    _sds_cache_at = time.monotonic()

    if _last_robot is not None and time.monotonic() - _last_robot_at <= ROBOT_LIVE_TTL_SECONDS:
        data = copy.deepcopy(_last_robot)
    else:
        data = TelemetryIn().model_dump()
        data["modo"] = "monitoreo_sensores"
        data["estado"] = "online"

    return await _publish(data)


@app.get("/api/sensores/sds011")
async def sds011_sensors() -> dict[str, Any]:
    overlay = _sds011_overlay()
    overlay.pop("_active", None)
    return {"sensores": overlay}


@app.get("/api/sensores/esp32")
async def esp32_sensors() -> dict[str, Any]:
    return {"sensores": _sensor_overlay()}


@app.get("/api/estado")
async def current_state() -> dict[str, Any]:
    return _live_state()


@app.get("/api/registros")
async def records(
    limit: int = Query(100, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    movimiento: str | None = None,
    gesto: str | None = None,
) -> dict[str, Any]:
    items = list_records(
        limit=limit,
        offset=offset,
        movimiento=movimiento,
        gesto=gesto,
    )

    return {
        "items": items,
        "limit": limit,
        "offset": offset,
    }


@app.delete("/api/registros/{record_id}")
async def remove_record(record_id: int) -> dict[str, Any]:
    deleted = delete_record(record_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Registro no encontrado",
        )

    return {
        "ok": True,
        "deleted_id": record_id,
    }


@app.delete("/api/registros")
async def remove_all_records() -> dict[str, Any]:
    count = delete_all_records()

    return {
        "ok": True,
        "deleted": count,
    }


@app.get("/api/estadisticas")
async def statistics() -> dict[str, Any]:
    result = stats()
    result["websocket_clients"] = len(manager.active)
    result["store_interval_seconds"] = STORE_INTERVAL_SECONDS
    return result


@app.get("/api/registros/export.csv")
async def export_csv() -> PlainTextResponse:
    return PlainTextResponse(
        export_csv_text(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="salud_ambiental_registros.csv"'
        },
    )


@app.websocket("/ws/telemetria")
async def telemetry_ws(websocket: WebSocket) -> None:
    await manager.connect(websocket)

    await websocket.send_json(_live_state())

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

if FRONTEND_DIST.exists():
    app.mount(
        "/",
        StaticFiles(
            directory=str(FRONTEND_DIST),
            html=True,
        ),
        name="frontend",
    )
