import csv
import io
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = Path(
    os.getenv("SIGAIRE_DATA_DIR", os.getenv("SINGARE_DATA_DIR", str(BACKEND_DIR / "data")))
)
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "singare.db"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def _ensure_columns(conn: sqlite3.Connection) -> None:
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(telemetry)").fetchall()
    }

    columns = {
        "pm25_raw": "REAL",
        "pm10_raw": "REAL",
        "pm25_filtered": "REAL",
        "pm10_filtered": "REAL",
        "pm25_std": "REAL",
        "pm10_std": "REAL",
        "pm25_min": "REAL",
        "pm25_max": "REAL",
        "pm10_min": "REAL",
        "pm10_max": "REAL",
        "sds011_estado": "TEXT DEFAULT 'SIN_DATOS'",
        "sds011_calibracion": "TEXT DEFAULT 'FABRICA'",
        "sds011_muestras": "INTEGER DEFAULT 0",
        "sds011_id": "TEXT DEFAULT ''",
        "sds011_outliers": "INTEGER DEFAULT 0",
    }

    for name, definition in columns.items():
        if name not in existing:
            conn.execute(
                f"ALTER TABLE telemetry ADD COLUMN {name} {definition}"
            )


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                robot TEXT NOT NULL,
                estado TEXT NOT NULL,
                modo TEXT,
                movimiento TEXT NOT NULL,
                gesto TEXT,
                esp32 TEXT,

                izquierda REAL DEFAULT 0,
                centro REAL DEFAULT 0,
                derecha REAL DEFAULT 0,
                objeto TEXT,
                confianza REAL DEFAULT 0,
                brillo REAL DEFAULT 0,
                blur REAL DEFAULT 0,

                pm25 REAL,
                pm10 REAL,

                pm25_raw REAL,
                pm10_raw REAL,
                pm25_filtered REAL,
                pm10_filtered REAL,
                pm25_std REAL,
                pm10_std REAL,
                pm25_min REAL,
                pm25_max REAL,
                pm10_min REAL,
                pm10_max REAL,

                sds011_estado TEXT DEFAULT 'SIN_DATOS',
                sds011_calibracion TEXT DEFAULT 'FABRICA',
                sds011_muestras INTEGER DEFAULT 0,
                sds011_id TEXT DEFAULT '',
                sds011_outliers INTEGER DEFAULT 0,

                co2 REAL,
                temperatura REAL,
                humedad REAL,
                presion REAL,

                raw_json TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp
            ON telemetry(timestamp DESC);

            CREATE INDEX IF NOT EXISTS idx_telemetry_movimiento
            ON telemetry(movimiento);

            CREATE INDEX IF NOT EXISTS idx_telemetry_gesto
            ON telemetry(gesto);
            """
        )

        _ensure_columns(conn)


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None

    record = dict(row)
    raw_json = record.pop("raw_json", None)

    try:
        raw = json.loads(raw_json) if raw_json else {}
    except json.JSONDecodeError:
        raw = {}

    record["vision"] = {
        "izquierda": record.pop("izquierda", 0.0),
        "centro": record.pop("centro", 0.0),
        "derecha": record.pop("derecha", 0.0),
        "objeto": record.pop("objeto", "") or "",
        "confianza": record.pop("confianza", 0.0) or 0.0,
        "brillo": record.pop("brillo", 0.0) or 0.0,
        "blur": record.pop("blur", 0.0) or 0.0,
    }

    record["sensores"] = {
        "pm25": record.pop("pm25", None),
        "pm10": record.pop("pm10", None),

        "pm25_raw": record.pop("pm25_raw", None),
        "pm10_raw": record.pop("pm10_raw", None),

        "pm25_filtered": record.pop("pm25_filtered", None),
        "pm10_filtered": record.pop("pm10_filtered", None),

        "pm25_std": record.pop("pm25_std", None),
        "pm10_std": record.pop("pm10_std", None),

        "pm25_min": record.pop("pm25_min", None),
        "pm25_max": record.pop("pm25_max", None),
        "pm10_min": record.pop("pm10_min", None),
        "pm10_max": record.pop("pm10_max", None),

        "sds011_estado": record.pop("sds011_estado", "SIN_DATOS") or "SIN_DATOS",
        "sds011_calibracion": record.pop("sds011_calibracion", "FABRICA") or "FABRICA",
        "sds011_muestras": record.pop("sds011_muestras", 0) or 0,
        "sds011_id": record.pop("sds011_id", "") or "",
        "sds011_outliers": record.pop("sds011_outliers", 0) or 0,

        "co2": record.pop("co2", None),
        "temperatura": record.pop("temperatura", None),
        "humedad": record.pop("humedad", None),
        "presion": record.pop("presion", None),
    }

    # Los nuevos sensores viven en raw_json para mantener compatibilidad
    # con las bases SQLite existentes sin perder sus datos históricos.
    for clave, valor in (raw.get("sensores") or {}).items():
        if clave not in record["sensores"]:
            record["sensores"][clave] = valor

    record["ruta"] = raw.get("ruta") or {}
    record["motores_visual"] = raw.get("motores_visual") or {}
    record["yolo"] = raw.get("yolo") or {}

    record["extra"] = {
        k: v
        for k, v in raw.items()
        if k not in {
            "robot", "estado", "modo", "movimiento", "gesto",
            "esp32", "vision", "sensores", "timestamp",
            "ruta", "motores_visual", "yolo"
        }
    }

    return record


def insert_telemetry(payload: dict[str, Any]) -> dict[str, Any]:
    timestamp = payload.get("timestamp") or datetime.now().astimezone().isoformat(timespec="milliseconds")
    vision = payload.get("vision") or {}
    sensores = payload.get("sensores") or {}

    values = (
        timestamp,
        payload.get("robot", "MeteoBot"),
        payload.get("estado", "offline"),
        payload.get("modo", ""),
        payload.get("movimiento", "STOP"),
        payload.get("gesto", "AUTONOMO"),
        payload.get("esp32", "desconectado"),

        vision.get("izquierda", 0.0),
        vision.get("centro", 0.0),
        vision.get("derecha", 0.0),
        vision.get("objeto", ""),
        vision.get("confianza", 0.0),
        vision.get("brillo", 0.0),
        vision.get("blur", 0.0),

        sensores.get("pm25"),
        sensores.get("pm10"),

        sensores.get("pm25_raw"),
        sensores.get("pm10_raw"),
        sensores.get("pm25_filtered"),
        sensores.get("pm10_filtered"),
        sensores.get("pm25_std"),
        sensores.get("pm10_std"),
        sensores.get("pm25_min"),
        sensores.get("pm25_max"),
        sensores.get("pm10_min"),
        sensores.get("pm10_max"),

        sensores.get("sds011_estado", "SIN_DATOS"),
        sensores.get("sds011_calibracion", "FABRICA"),
        sensores.get("sds011_muestras", 0),
        sensores.get("sds011_id", ""),
        sensores.get("sds011_outliers", 0),

        sensores.get("co2"),
        sensores.get("temperatura"),
        sensores.get("humedad"),
        sensores.get("presion"),

        json.dumps(payload, ensure_ascii=False),
    )

    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO telemetry (
                timestamp, robot, estado, modo, movimiento, gesto, esp32,
                izquierda, centro, derecha, objeto, confianza, brillo, blur,
                pm25, pm10,
                pm25_raw, pm10_raw,
                pm25_filtered, pm10_filtered,
                pm25_std, pm10_std,
                pm25_min, pm25_max, pm10_min, pm10_max,
                sds011_estado, sds011_calibracion,
                sds011_muestras, sds011_id, sds011_outliers,
                co2, temperatura, humedad, presion,
                raw_json
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?,
                ?, ?,
                ?, ?,
                ?, ?,
                ?, ?, ?, ?,
                ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?
            )
            """,
            values,
        )

        new_id = cursor.lastrowid

        row = conn.execute(
            "SELECT * FROM telemetry WHERE id = ?",
            (new_id,),
        ).fetchone()

    return _row_to_dict(row) or {}


def latest_record() -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM telemetry ORDER BY id DESC LIMIT 1"
        ).fetchone()

    return _row_to_dict(row)


def list_records(
    limit: int = 100,
    offset: int = 0,
    movimiento: str | None = None,
    gesto: str | None = None,
) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 2000))
    offset = max(0, offset)

    clauses: list[str] = []
    params: list[Any] = []

    if movimiento:
        clauses.append("movimiento = ?")
        params.append(movimiento)

    if gesto:
        clauses.append("gesto = ?")
        params.append(gesto)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    query = f"""
        SELECT *
        FROM telemetry
        {where}
        ORDER BY id DESC
        LIMIT ? OFFSET ?
    """

    params.extend([limit, offset])

    with connect() as conn:
        rows = conn.execute(query, params).fetchall()

    return [_row_to_dict(row) for row in rows if row is not None]


def delete_record(record_id: int) -> bool:
    with connect() as conn:
        cursor = conn.execute(
            "DELETE FROM telemetry WHERE id = ?",
            (record_id,),
        )

    return cursor.rowcount > 0


def delete_all_records() -> int:
    with connect() as conn:
        cursor = conn.execute("DELETE FROM telemetry")
        conn.execute("DELETE FROM sqlite_sequence WHERE name = 'telemetry'")

    return cursor.rowcount


def stats() -> dict[str, Any]:
    with connect() as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM telemetry"
        ).fetchone()["c"]

        latest = conn.execute(
            "SELECT timestamp FROM telemetry ORDER BY id DESC LIMIT 1"
        ).fetchone()

        movement_rows = conn.execute(
            """
            SELECT movimiento, COUNT(*) AS cantidad
            FROM telemetry
            GROUP BY movimiento
            ORDER BY cantidad DESC
            """
        ).fetchall()

        particle = conn.execute(
            """
            SELECT
                AVG(pm25) AS pm25_avg,
                AVG(pm10) AS pm10_avg,
                MIN(pm25) AS pm25_min,
                MAX(pm25) AS pm25_max,
                MIN(pm10) AS pm10_min,
                MAX(pm10) AS pm10_max
            FROM telemetry
            WHERE pm25 IS NOT NULL OR pm10 IS NOT NULL
            """
        ).fetchone()

    db_size = DB_PATH.stat().st_size if DB_PATH.exists() else 0

    return {
        "records": count,
        "database_path": str(DB_PATH),
        "database_size_bytes": db_size,
        "last_record": latest["timestamp"] if latest else None,
        "movements": {
            row["movimiento"]: row["cantidad"]
            for row in movement_rows
        },
        "particles": dict(particle) if particle else {},
    }


def export_csv_text() -> str:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM telemetry ORDER BY id ASC"
        ).fetchall()

    buffer = io.StringIO()
    writer = csv.writer(buffer)

    writer.writerow(
        [
            "id", "timestamp", "robot", "estado", "modo", "movimiento",
            "gesto", "esp32", "izquierda", "centro", "derecha",
            "objeto", "confianza", "brillo", "blur",
            "pm25", "pm10",
            "pm25_raw", "pm10_raw",
            "pm25_filtered", "pm10_filtered",
            "pm25_std", "pm10_std",
            "pm25_min", "pm25_max", "pm10_min", "pm10_max",
            "sds011_estado", "sds011_calibracion",
            "sds011_muestras", "sds011_id", "sds011_outliers",
            "co2", "temperatura", "humedad", "presion",
            "esp32_sensor_estado", "sht3x_estado", "sharp_estado", "sharp_vo_v",
            "sharp_adc_mv", "sharp_raw", "bfs302_estado", "bfs302_aout_v",
            "bfs302_adc_mv", "bfs302_raw", "bfs302_dout",
            "mg811_estado", "mg811_aout_v", "mg811_adc_mv", "mg811_raw",
            "mg811_calibrado", "mg811_estable_10min", "mg811_evento_senal",
            "mg811_delta_aout_mv", "mg811_error_validacion_pct"
        ]
    )

    for row in rows:
        try:
            sensor_extra = (json.loads(row["raw_json"] or "{}").get("sensores") or {})
        except (ValueError, TypeError):
            sensor_extra = {}
        writer.writerow(
            [
                row["id"], row["timestamp"], row["robot"], row["estado"],
                row["modo"], row["movimiento"], row["gesto"], row["esp32"],
                row["izquierda"], row["centro"], row["derecha"],
                row["objeto"], row["confianza"], row["brillo"], row["blur"],
                row["pm25"], row["pm10"],
                row["pm25_raw"], row["pm10_raw"],
                row["pm25_filtered"], row["pm10_filtered"],
                row["pm25_std"], row["pm10_std"],
                row["pm25_min"], row["pm25_max"],
                row["pm10_min"], row["pm10_max"],
                row["sds011_estado"], row["sds011_calibracion"],
                row["sds011_muestras"], row["sds011_id"],
                row["sds011_outliers"],
                row["co2"], row["temperatura"],
                row["humedad"], row["presion"],
                *[sensor_extra.get(key) for key in (
                    "esp32_sensor_estado", "sht3x_estado", "sharp_estado",
                    "sharp_vo_v", "sharp_adc_mv", "sharp_raw", "bfs302_estado",
                    "bfs302_aout_v", "bfs302_adc_mv", "bfs302_raw", "bfs302_dout",
                    "mg811_estado", "mg811_aout_v", "mg811_adc_mv", "mg811_raw",
                    "mg811_calibrado", "mg811_estable_10min", "mg811_evento_senal",
                    "mg811_delta_aout_mv", "mg811_error_validacion_pct"
                )],
            ]
        )

    return buffer.getvalue()
