#!/usr/bin/env python3

import argparse
import csv
import json
from pathlib import Path

import numpy as np


def load_csv(path):
    pm25_sensor = []
    pm25_ref = []
    pm10_sensor = []
    pm10_ref = []

    with Path(path).open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as handle:

        reader = csv.DictReader(
            handle
        )

        required = {
            "pm25_sensor",
            "pm25_referencia",
            "pm10_sensor",
            "pm10_referencia",
        }

        missing = (
            required
            - set(
                reader.fieldnames
                or []
            )
        )

        if missing:
            raise ValueError(
                "Faltan columnas: "
                + ", ".join(
                    sorted(
                        missing
                    )
                )
            )

        for row in reader:
            try:
                p25s = float(
                    row["pm25_sensor"]
                )
                p25r = float(
                    row["pm25_referencia"]
                )
                p10s = float(
                    row["pm10_sensor"]
                )
                p10r = float(
                    row["pm10_referencia"]
                )
            except (
                TypeError,
                ValueError,
            ):
                continue

            if min(
                p25s,
                p25r,
                p10s,
                p10r,
            ) < 0:
                continue

            pm25_sensor.append(
                p25s
            )
            pm25_ref.append(
                p25r
            )
            pm10_sensor.append(
                p10s
            )
            pm10_ref.append(
                p10r
            )

    return (
        np.asarray(
            pm25_sensor,
            dtype=float
        ),
        np.asarray(
            pm25_ref,
            dtype=float
        ),
        np.asarray(
            pm10_sensor,
            dtype=float
        ),
        np.asarray(
            pm10_ref,
            dtype=float
        ),
    )


def fit(sensor, reference):
    if sensor.size < 20:
        raise ValueError(
            "Se recomiendan al menos 20 pares válidos "
            "para calcular una calibración."
        )

    if np.ptp(sensor) < 5:
        raise ValueError(
            "El rango de concentraciones del conjunto es demasiado pequeño. "
            "Realiza la comparación en distintos niveles de PM."
        )

    slope, intercept = np.polyfit(
        sensor,
        reference,
        1
    )

    predicted = (
        slope * sensor
        + intercept
    )

    residual = (
        reference
        - predicted
    )

    ss_res = float(
        np.sum(
            residual ** 2
        )
    )

    ss_tot = float(
        np.sum(
            (
                reference
                - np.mean(reference)
            ) ** 2
        )
    )

    r2 = (
        1.0
        - ss_res / ss_tot
        if ss_tot > 0
        else 0.0
    )

    rmse = float(
        np.sqrt(
            np.mean(
                residual ** 2
            )
        )
    )

    return {
        "slope": float(
            slope
        ),
        "intercept": float(
            intercept
        ),
        "r2": r2,
        "rmse": rmse,
        "n": int(
            sensor.size
        ),
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Calcula coeficientes lineales para SDS011 "
            "a partir de mediciones simultáneas con un instrumento de referencia."
        )
    )

    parser.add_argument(
        "csv",
        help="CSV de comparación."
    )

    parser.add_argument(
        "--output",
        default=str(
            Path(__file__).resolve().parent
            / "sds011_calibration.json"
        ),
        help="Archivo JSON de calibración de salida."
    )

    args = parser.parse_args()

    (
        pm25_sensor,
        pm25_ref,
        pm10_sensor,
        pm10_ref,
    ) = load_csv(
        args.csv
    )

    pm25 = fit(
        pm25_sensor,
        pm25_ref
    )

    pm10 = fit(
        pm10_sensor,
        pm10_ref
    )

    output_path = Path(
        args.output
    )

    existing = {}

    if output_path.exists():
        try:
            existing = json.loads(
                output_path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            existing = {}

    config = {
        "version": 1,
        "description": (
            "Coeficientes obtenidos por regresión lineal "
            "contra un instrumento de referencia."
        ),
        "pm25": {
            "slope": pm25["slope"],
            "intercept": pm25["intercept"],
        },
        "pm10": {
            "slope": pm10["slope"],
            "intercept": pm10["intercept"],
        },
        "filter": existing.get(
            "filter",
            {
                "warmup_seconds": 60,
                "window_size": 15,
                "ema_alpha": 0.35,
                "mad_sigma": 3.5,
                "min_valid_samples": 5,
                "stale_seconds": 5,
            }
        ),
        "fit_quality": {
            "pm25": {
                "r2": pm25["r2"],
                "rmse": pm25["rmse"],
                "n": pm25["n"],
            },
            "pm10": {
                "r2": pm10["r2"],
                "rmse": pm10["rmse"],
                "n": pm10["n"],
            },
        },
    }

    output_path.write_text(
        json.dumps(
            config,
            ensure_ascii=False,
            indent=2
        )
        + "\n",
        encoding="utf-8"
    )

    print()
    print(
        "==============================================="
    )
    print(
        " CALIBRACION SDS011 -> INSTRUMENTO REFERENCIA"
    )
    print(
        "==============================================="
    )

    print(
        f"PM2.5: y = "
        f"{pm25['slope']:.6f} x "
        f"{pm25['intercept']:+.6f}"
    )
    print(
        f"       R²={pm25['r2']:.4f} "
        f"RMSE={pm25['rmse']:.3f} "
        f"N={pm25['n']}"
    )

    print(
        f"PM10 : y = "
        f"{pm10['slope']:.6f} x "
        f"{pm10['intercept']:+.6f}"
    )
    print(
        f"       R²={pm10['r2']:.4f} "
        f"RMSE={pm10['rmse']:.3f} "
        f"N={pm10['n']}"
    )

    print()
    print(
        "Guardado en:",
        output_path
    )
    print()
    print(
        "Reinicia el lector de MeteoBot para aplicar "
        "los nuevos coeficientes."
    )


if __name__ == "__main__":
    main()
