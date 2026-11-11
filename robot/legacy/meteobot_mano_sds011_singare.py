#!/usr/bin/env python3

from picamera2 import Picamera2
import cv2
import numpy as np
import requests
import math
import time
import signal
import sys

from sds011_reader import SDS011Reader


# ============================================================
# METEOBOT + SINGARE V4
#
# AI Camera -> gesto de mano -> ESP32 -> 4 motores
# SDS011 -> PM2.5 / PM10
# Todo -> SINGARE -> dashboard web en tiempo real
# ============================================================


# ============================================================
# RED
# ============================================================

ESP32_IP = "192.168.137.251"

URL_AVANZAR = f"http://{ESP32_IP}/avanzar"
URL_STOP = f"http://{ESP32_IP}/stop"

# SINGARE se ejecuta en esta misma Raspberry Pi.
# Usar loopback evita depender de que cambie la IP local.
SINGARE_URL = "http://127.0.0.1:5000/api/telemetria"

DASHBOARD_URL = "http://192.168.137.41:5000/"


# ============================================================
# SDS011
# ============================================================

# None = autodeteccion de /dev/serial/by-id o /dev/ttyUSB*
# El calentamiento, ventana, EMA y coeficientes se configuran en
# sds011_calibration.json
SDS011_PORT = None


# ============================================================
# CAMARA
# ============================================================

ANCHO = 640
ALTO = 480
FPS = 30
MOSTRAR_CAMARA = True


# ============================================================
# GESTO
# ============================================================

AREA_MINIMA = 4500
PORCENTAJE_AREA_MAXIMA = 0.70

FRAMES_AVANZAR = 8
FRAMES_STOP = 2

ROI_X1 = 300
ROI_Y1 = 100
ROI_X2 = 620
ROI_Y2 = 450


# ============================================================
# COMUNICACION
# ============================================================

INTERVALO_MOTOR = 0.25
INTERVALO_SINGARE = 0.40
TIMEOUT_HTTP = 0.35


# ============================================================
# ESTADO
# ============================================================

estado = "STOP"
gesto = "SIN_MANO"

contador_abierta = 0
contador_stop = 0

ultimo_motor = 0.0
ultimo_singare = 0.0

esp32_estado = "desconectado"

ejecutando = True

picam2 = None
sds011 = None


# ============================================================
# ESP32
# ============================================================

def post_esp32(url):

    global esp32_estado

    try:

        respuesta = requests.post(
            url,
            timeout=TIMEOUT_HTTP
        )

        if respuesta.status_code == 200:

            esp32_estado = "conectado"

            return True

    except requests.RequestException:

        pass


    esp32_estado = "desconectado"

    return False


def enviar_avanzar():

    return post_esp32(
        URL_AVANZAR
    )


def enviar_stop():

    return post_esp32(
        URL_STOP
    )


# ============================================================
# SINGARE
# ============================================================

def enviar_singare(
    movimiento,
    gesto_actual,
    area,
    defectos,
    solidity,
    extent,
    brillo,
    blur,
    sensor_data
):

    datos = {

        "robot":
            "MeteoBot",

        "estado":
            "online",

        "modo":
            "control_gestual_sds011",

        "movimiento":
            movimiento,

        "gesto":
            gesto_actual,

        "esp32":
            esp32_estado,

        "vision": {

            "izquierda":
                0.0,

            "centro":
                0.0,

            "derecha":
                0.0,

            "objeto":
                "mano"
                if gesto_actual != "SIN_MANO"
                else "",

            "confianza":
                1.0
                if gesto_actual == "MANO_ABIERTA"
                else 0.0,

            "brillo":
                float(brillo),

            "blur":
                float(blur),

            "area_mano":
                float(area),

            "defectos":
                int(defectos),

            "solidity":
                float(solidity),

            "extent":
                float(extent)
        },

        "sensores": {

            "pm25":
                sensor_data.get(
                    "pm25"
                ),

            "pm10":
                sensor_data.get(
                    "pm10"
                ),

            "pm25_raw":
                sensor_data.get(
                    "pm25_raw"
                ),

            "pm10_raw":
                sensor_data.get(
                    "pm10_raw"
                ),

            "pm25_filtered":
                sensor_data.get(
                    "pm25_filtered"
                ),

            "pm10_filtered":
                sensor_data.get(
                    "pm10_filtered"
                ),

            "pm25_std":
                sensor_data.get(
                    "pm25_std"
                ),

            "pm10_std":
                sensor_data.get(
                    "pm10_std"
                ),

            "pm25_min":
                sensor_data.get(
                    "pm25_min"
                ),

            "pm25_max":
                sensor_data.get(
                    "pm25_max"
                ),

            "pm10_min":
                sensor_data.get(
                    "pm10_min"
                ),

            "pm10_max":
                sensor_data.get(
                    "pm10_max"
                ),

            "sds011_estado":
                sensor_data.get(
                    "sds011_estado",
                    "SIN_DATOS"
                ),

            "sds011_calibracion":
                sensor_data.get(
                    "sds011_calibracion",
                    "FABRICA"
                ),

            "sds011_muestras":
                sensor_data.get(
                    "sds011_muestras",
                    0
                ),

            "sds011_outliers":
                sensor_data.get(
                    "sds011_outliers",
                    0
                ),

            "sds011_id":
                sensor_data.get(
                    "sds011_id",
                    ""
                ),

            "sds011_puerto":
                sensor_data.get(
                    "sds011_puerto",
                    ""
                ),

            "sds011_calentamiento_restante":
                sensor_data.get(
                    "sds011_calentamiento_restante"
                ),

            "sds011_edad_lectura_s":
                sensor_data.get(
                    "sds011_edad_lectura_s"
                ),

            "co2":
                None,

            "temperatura":
                None,

            "humedad":
                None,

            "presion":
                None
        }
    }


    try:

        requests.post(
            SINGARE_URL,
            json=datos,
            timeout=0.25
        )

    except requests.RequestException:

        pass


# ============================================================
# PARADA SEGURA
# ============================================================

def parada_segura():

    global ejecutando

    ejecutando = False


    for _ in range(3):

        try:

            requests.post(
                URL_STOP,
                timeout=0.20
            )

        except requests.RequestException:

            pass


        time.sleep(
            0.05
        )


def manejar_senal(
    signum,
    frame
):

    print()
    print(
        f"[SISTEMA] Señal {signum}. STOP de seguridad."
    )

    parada_segura()


signal.signal(
    signal.SIGINT,
    manejar_senal
)

signal.signal(
    signal.SIGTERM,
    manejar_senal
)


# ============================================================
# DEFECTOS DE CONVEXIDAD
# ============================================================

def contar_defectos(
    contorno
):

    hull_indices = cv2.convexHull(
        contorno,
        returnPoints=False
    )


    if (
        hull_indices is None
        or
        len(hull_indices) < 4
    ):

        return 0


    defectos = cv2.convexityDefects(
        contorno,
        hull_indices
    )


    if defectos is None:

        return 0


    contador = 0


    for i in range(
        defectos.shape[0]
    ):

        s, e, f, d = (
            defectos[i, 0]
        )


        inicio = (
            contorno[s][0]
        )

        fin = (
            contorno[e][0]
        )

        fondo = (
            contorno[f][0]
        )


        a = math.dist(
            inicio,
            fin
        )

        b = math.dist(
            inicio,
            fondo
        )

        c = math.dist(
            fin,
            fondo
        )


        if b == 0 or c == 0:

            continue


        coseno = (
            b * b
            +
            c * c
            -
            a * a

        ) / (

            2
            *
            b
            *
            c
        )


        coseno = max(
            -1.0,
            min(
                1.0,
                coseno
            )
        )


        angulo = math.degrees(
            math.acos(
                coseno
            )
        )


        profundidad = (
            d
            /
            256.0
        )


        if (
            angulo < 90
            and
            profundidad > 15
        ):

            contador += 1


    return contador


# ============================================================
# ANALISIS DE MANO
# ============================================================

def analizar_mano(
    frame
):

    roi = frame[
        ROI_Y1:ROI_Y2,
        ROI_X1:ROI_X2
    ]


    ycrcb = cv2.cvtColor(
        roi,
        cv2.COLOR_RGB2YCrCb
    )


    inferior = np.array(
        [0, 133, 77],
        dtype=np.uint8
    )


    superior = np.array(
        [255, 173, 127],
        dtype=np.uint8
    )


    mascara = cv2.inRange(
        ycrcb,
        inferior,
        superior
    )


    mascara = cv2.GaussianBlur(
        mascara,
        (7, 7),
        0
    )


    kernel = np.ones(
        (5, 5),
        np.uint8
    )


    mascara = cv2.morphologyEx(
        mascara,
        cv2.MORPH_OPEN,
        kernel
    )


    mascara = cv2.morphologyEx(
        mascara,
        cv2.MORPH_CLOSE,
        kernel
    )


    contornos, _ = cv2.findContours(
        mascara,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )


    if not contornos:

        return (
            "SIN_MANO",
            mascara,
            None,
            0,
            0.0,
            0.0,
            0.0
        )


    contorno = max(
        contornos,
        key=cv2.contourArea
    )


    area = float(
        cv2.contourArea(
            contorno
        )
    )


    area_roi = (
        roi.shape[0]
        *
        roi.shape[1]
    )


    porcentaje_area = (
        area
        /
        area_roi
    )


    if (
        area < AREA_MINIMA
        or
        porcentaje_area >
        PORCENTAJE_AREA_MAXIMA
    ):

        return (
            "SIN_MANO",
            mascara,
            None,
            0,
            area,
            0.0,
            0.0
        )


    x, y, w, h = (
        cv2.boundingRect(
            contorno
        )
    )


    if (
        w < 55
        or
        h < 55
    ):

        return (
            "SIN_MANO",
            mascara,
            contorno,
            0,
            area,
            0.0,
            0.0
        )


    hull = cv2.convexHull(
        contorno
    )


    area_hull = float(
        cv2.contourArea(
            hull
        )
    )


    if area_hull <= 0:

        return (
            "SIN_MANO",
            mascara,
            contorno,
            0,
            area,
            0.0,
            0.0
        )


    solidity = (
        area
        /
        area_hull
    )


    extent = (
        area
        /
        float(
            w * h
        )
    )


    defectos = contar_defectos(
        contorno
    )


    mano_abierta = (
        defectos >= 3
        and
        solidity < 0.88
        and
        extent < 0.80
    )


    candidato = (
        "MANO_ABIERTA"
        if mano_abierta
        else
        "PUNO"
    )


    return (
        candidato,
        mascara,
        contorno,
        defectos,
        area,
        solidity,
        extent
    )


# ============================================================
# CALIDAD DE IMAGEN
# ============================================================

def calidad_imagen(
    frame
):

    bgr = cv2.cvtColor(
        frame,
        cv2.COLOR_RGB2BGR
    )


    gris = cv2.cvtColor(
        bgr,
        cv2.COLOR_BGR2GRAY
    )


    brillo = float(
        np.mean(
            gris
        )
    )


    blur = float(
        cv2.Laplacian(
            gris,
            cv2.CV_64F
        ).var()
    )


    return (
        brillo,
        blur
    )


# ============================================================
# CAMARA
# ============================================================

def iniciar_camara():

    global picam2


    picam2 = Picamera2()


    config = (
        picam2.create_video_configuration(

            main={

                "format":
                    "RGB888",

                "size":
                    (
                        ANCHO,
                        ALTO
                    )
            },

            controls={

                "FrameRate":
                    FPS
            }
        )
    )


    picam2.configure(
        config
    )


    picam2.start()


    time.sleep(
        1.5
    )


# ============================================================
# PRINCIPAL
# ============================================================

def main():

    global estado
    global gesto

    global contador_abierta
    global contador_stop

    global ultimo_motor
    global ultimo_singare

    global sds011


    print()
    print(
        "=================================================="
    )
    print(
        " METEOBOT + SDS011 + SINGARE V3"
    )
    print(
        "=================================================="
    )
    print(
        f"ESP32:     {ESP32_IP}"
    )
    print(
        f"Dashboard: {DASHBOARD_URL}"
    )
    print()
    print(
        "MANO ABIERTA -> AVANZAR PWM 180"
    )
    print(
        "PUNO / SIN MANO -> STOP"
    )
    print(
        "SDS011 -> PM2.5 / PM10 -> SINGARE"
    )
    print()


    # ========================================================
    # SENSOR SDS011
    # ========================================================

    sds011 = SDS011Reader(
        port=SDS011_PORT
    )


    sds011.start()


    print(
        f"SDS011: {sds011.port}"
    )


    # ========================================================
    # CAMARA
    # ========================================================

    iniciar_camara()


    # Estado inicial seguro.
    enviar_stop()


    while ejecutando:


        frame = (
            picam2.capture_array()
        )


        (
            candidato,
            mascara,
            contorno,
            defectos,
            area,
            solidity,
            extent

        ) = analizar_mano(
            frame
        )


        (
            brillo,
            blur

        ) = calidad_imagen(
            frame
        )


        # ====================================================
        # FILTRO DE GESTO
        # ====================================================

        if candidato == "MANO_ABIERTA":

            contador_abierta += 1

            contador_stop = 0


            if (
                contador_abierta
                >=
                FRAMES_AVANZAR
            ):

                gesto = (
                    "MANO_ABIERTA"
                )

                estado = (
                    "AVANZAR"
                )


        else:

            contador_abierta = 0

            contador_stop += 1


            if (
                contador_stop
                >=
                FRAMES_STOP
            ):

                gesto = candidato

                estado = "STOP"


        ahora = time.monotonic()


        # ====================================================
        # MOTORES
        # ====================================================

        if (
            ahora
            -
            ultimo_motor
            >=
            INTERVALO_MOTOR
        ):

            if estado == "AVANZAR":

                correcto = (
                    enviar_avanzar()
                )


                if not correcto:

                    estado = "STOP"

                    enviar_stop()


            else:

                enviar_stop()


            ultimo_motor = ahora


        # ====================================================
        # SDS011
        # ====================================================

        sensor_data = (
            sds011.snapshot()
        )


        # ====================================================
        # SINGARE
        # ====================================================

        if (
            ahora
            -
            ultimo_singare
            >=
            INTERVALO_SINGARE
        ):

            enviar_singare(

                movimiento=
                    estado,

                gesto_actual=
                    gesto,

                area=
                    area,

                defectos=
                    defectos,

                solidity=
                    solidity,

                extent=
                    extent,

                brillo=
                    brillo,

                blur=
                    blur,

                sensor_data=
                    sensor_data
            )


            ultimo_singare = (
                ahora
            )


        # ====================================================
        # TERMINAL
        # ====================================================

        pm25 = sensor_data.get(
            "pm25"
        )

        pm10 = sensor_data.get(
            "pm10"
        )


        pm25_txt = (
            "--"
            if pm25 is None
            else
            f"{pm25:.1f}"
        )

        pm10_txt = (
            "--"
            if pm10 is None
            else
            f"{pm10:.1f}"
        )


        print(

            f"\rGESTO={gesto:12} | "
            f"CMD={estado:7} | "
            f"ESP32={esp32_estado:12} | "
            f"SDS={sensor_data.get('sds011_estado', '---'):12} | "
            f"PM2.5={pm25_txt:>6} | "
            f"PM10={pm10_txt:>6}",

            end="",

            flush=True
        )


        # ====================================================
        # VISTA LOCAL
        # ====================================================

        if MOSTRAR_CAMARA:


            vista = cv2.cvtColor(
                frame,
                cv2.COLOR_RGB2BGR
            )


            color = (
                (0, 255, 0)

                if estado == "AVANZAR"

                else

                (0, 0, 255)
            )


            cv2.rectangle(
                vista,
                (
                    ROI_X1,
                    ROI_Y1
                ),
                (
                    ROI_X2,
                    ROI_Y2
                ),
                color,
                3
            )


            if contorno is not None:

                offset = np.array(
                    [
                        [
                            [
                                ROI_X1,
                                ROI_Y1
                            ]
                        ]
                    ]
                )


                contorno_global = (
                    contorno
                    +
                    offset
                )


                cv2.drawContours(
                    vista,
                    [
                        contorno_global
                    ],
                    -1,
                    (
                        0,
                        255,
                        255
                    ),
                    2
                )


            cv2.putText(
                vista,
                f"GESTO: {gesto}",
                (
                    15,
                    35
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.70,
                color,
                2
            )


            cv2.putText(
                vista,
                f"CMD: {estado}",
                (
                    15,
                    65
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.70,
                color,
                2
            )


            cv2.putText(
                vista,
                f"PM2.5: {pm25_txt} ug/m3",
                (
                    15,
                    100
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (
                    255,
                    255,
                    255
                ),
                2
            )


            cv2.putText(
                vista,
                f"PM10: {pm10_txt} ug/m3",
                (
                    15,
                    125
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (
                    255,
                    255,
                    255
                ),
                2
            )


            cv2.imshow(
                "MeteoBot + SDS011 + SINGARE V3",
                vista
            )


            if (
                cv2.waitKey(1)
                &
                0xFF
            ) == ord("q"):

                break


# ============================================================
# EJECUCION
# ============================================================

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

                SINGARE_URL,

                json={

                    "robot":
                        "MeteoBot",

                    "estado":
                        "offline",

                    "modo":
                        "control_gestual_sds011",

                    "movimiento":
                        "STOP",

                    "gesto":
                        "SIN_MANO",

                    "esp32":
                        esp32_estado,

                    "vision": {

                        "izquierda":
                            0,

                        "centro":
                            0,

                        "derecha":
                            0,

                        "objeto":
                            "",

                        "confianza":
                            0,

                        "brillo":
                            0,

                        "blur":
                            0
                    },

                    "sensores":
                        sds011.snapshot()
                        if sds011 is not None
                        else
                        {
                            "pm25": None,
                            "pm10": None,
                            "sds011_estado": "SIN_DATOS"
                        }
                },

                timeout=
                    0.20
            )

        except requests.RequestException:

            pass


        print()
        print(
            "MeteoBot detenido de forma segura."
        )

        sys.exit(
            0
        )
