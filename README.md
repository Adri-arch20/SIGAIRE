# SALUD_AMBIENTAL_MeteoBot_v7

Versión V7 de la plataforma web de MeteoBot para monitoreo ambiental y navegación autónoma.

## Interfaz V7

La primera pantalla es la **vista principal para el usuario**. Su diseño toma la estructura visual del dashboard de referencia: encabezado vino/magenta, panel lateral de ubicación, tarjetas rosadas de variables ambientales y acceso separado al panel técnico.

Nombre visible de la plataforma: **SALUD AMBIENTAL**.

Paleta principal:
- Vino/magenta: `#A60049`
- Vino oscuro: `#83003B`
- Rosa de fondo: `#FFF2F7`
- Borde rosa: `#F58CBD`
- Texto: `#172033`

## Sensores integrados

- **SDS011 (Raspberry Pi):** PM2.5 y PM10.
- **SHT3x (ESP32):** temperatura y humedad relativa.
- **Sharp GP2Y1014 (ESP32):** Vo, ADC y RAW.
- **BFS-302 (ESP32):** AOUT, ADC, RAW y DOUT.
- **CO2:** la tarjeta está preparada, pero solo muestra ppm cuando el backend recibe un valor calibrado. No se generan ppm a partir de voltajes sin una curva validada.

La IP predeterminada del ESP32 es:

```text
192.168.137.200
```

## Instalación en Raspberry Pi 5

```bash
cd ~/Downloads/SALUD_AMBIENTAL_MeteoBot_v7
chmod +x scripts/*.sh
./scripts/install_raspberry.sh
```

El instalador elimina cualquier `node_modules` copiado desde Windows e instala nuevamente las dependencias para Raspberry Pi. Esto evita el error `vite: Permission denied`.

## Ejecutar solo la web

```bash
./scripts/run.sh
```

Abrir:

```text
http://localhost:5000
```

Desde otra computadora de la misma red:

```bash
hostname -I
```

Y abrir `http://IP_DE_LA_RASPBERRY:5000`.

## Ejecutar web + sensores ESP32

Primera vez:

```bash
./scripts/install_sensores.sh
```

Después:

```bash
./scripts/start_salud_ambiental_sensores.sh
```

También se conserva el alias anterior:

```bash
./scripts/start_sigaire_sensores.sh
```

## Ejecutar navegación autónoma

```bash
./scripts/run_robot_autonomo.sh
```

La navegación autónoma conserva el seguimiento de bordes amarillos, YOLO, evasión de obstáculos, SDS011 y watchdog de seguridad.

## Firmware ESP32 V7

Nuevo nombre recomendado:

```text
robot/esp32_salud_ambiental_v7/esp32_salud_ambiental_v7.ino
```

Se conserva la carpeta anterior para compatibilidad.

## Modo de prueba sin mover motores

Terminal 1:

```bash
./scripts/run.sh
```

Terminal 2:

```bash
python3 scripts/test_salud_ambiental.py
```

Este modo permite probar las tarjetas, animaciones, estados y gráficas de la interfaz sin enviar comandos físicos de movimiento.


## Correccion V7.1: SDS011 independiente

`./scripts/start_salud_ambiental_sensores.sh` inicia ahora tres procesos: web, puente ESP32 y puente SDS011. Por ello PM2.5 y PM10 se visualizan sin ejecutar YOLO ni el movimiento autonomo.

La IP ESP32 predeterminada es `192.168.137.200`. El SDS011 se autodetecta en `/dev/serial/by-id/*` o `/dev/ttyUSB0`; se puede fijar con `SDS011_PORT` en `config/sensores.env`.


## V7.2 · MG811 CO₂ e historial con scroll

- ESP32 esperado en `192.168.137.200`.
- MG811/OKY3352: AOUT mediante divisor 100 kΩ/100 kΩ hacia **GPIO35**; alimentación externa de 6 V y tierra común.
- El endpoint ESP32 `/sensores` incluye el objeto `mg811`; `/co2` expone el detalle del sensor.
- SALUD AMBIENTAL muestra `co2` en ppm solo cuando el firmware entrega una estimación calibrada; sin calibración conserva AOUT/ADC y el estado `SIN_CALIBRAR`.
- El historial tiene scroll vertical propio, cabecera fija y columnas CO₂/MG811 para evitar que la tabla salga del panel.
