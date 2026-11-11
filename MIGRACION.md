# Migración a SALUD_AMBIENTAL_MeteoBot_v7

La V7 conserva el backend, base de datos, puente de sensores, scripts de navegación autónoma y lógica de telemetría de V6. La modificación principal es el frontend y la robustez de instalación.

## De V6 a V7

No copies `node_modules` desde la versión anterior. En Raspberry Pi ejecuta:

```bash
cd ~/Downloads/SALUD_AMBIENTAL_MeteoBot_v7
chmod +x scripts/*.sh
./scripts/install_raspberry.sh
```

Si ya tienes configuración de sensores y deseas reutilizarla, copia únicamente tu archivo `config/sensores.env` y comprueba:

```text
METEOBOT_ESP32_IP=192.168.137.200
```

Después inicia:

```bash
./scripts/start_salud_ambiental_sensores.sh
```


## Correccion V7.1: SDS011 independiente

`./scripts/start_salud_ambiental_sensores.sh` inicia ahora tres procesos: web, puente ESP32 y puente SDS011. Por ello PM2.5 y PM10 se visualizan sin ejecutar YOLO ni el movimiento autonomo.

La IP ESP32 predeterminada es `192.168.137.200`. El SDS011 se autodetecta en `/dev/serial/by-id/*` o `/dev/ttyUSB0`; se puede fijar con `SDS011_PORT` en `config/sensores.env`.
