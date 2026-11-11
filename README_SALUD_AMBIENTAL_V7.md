# SALUD AMBIENTAL · MeteoBot V7

## Cambios principales respecto a V6

1. La vista inicial adopta el dashboard público vino/magenta solicitado.
2. El nombre visible es **SALUD AMBIENTAL** en toda la interfaz.
3. La paleta vino/magenta se extiende también al panel técnico.
4. La ubicación de MeteoBot se muestra en una columna lateral con mapa de referencia.
5. PM2.5, PM10, CO2 y temperatura/humedad aparecen como métricas principales.
6. Sharp GP2Y1014 y BFS-302 aparecen como sensores secundarios interactivos.
7. CO2 no muestra ppm hasta que exista una lectura calibrada.
8. Las tarjetas abren una explicación interactiva al hacer clic.
9. Se añadieron menú lateral, panel rápido de estado, animaciones de conexión, recomendación ambiental y tendencia PM2.5.
10. El instalador V7 corrige instalaciones con `node_modules` provenientes de Windows y evita `vite: Permission denied`.
11. La IP ESP32 predeterminada se mantiene en `192.168.137.200`.

## Inicio rápido

```bash
cd ~/Downloads/SALUD_AMBIENTAL_MeteoBot_v7
chmod +x scripts/*.sh
./scripts/install_raspberry.sh
./scripts/start_salud_ambiental_sensores.sh
```


## Correccion V7.1: SDS011 independiente

`./scripts/start_salud_ambiental_sensores.sh` inicia ahora tres procesos: web, puente ESP32 y puente SDS011. Por ello PM2.5 y PM10 se visualizan sin ejecutar YOLO ni el movimiento autonomo.

La IP ESP32 predeterminada es `192.168.137.200`. El SDS011 se autodetecta en `/dev/serial/by-id/*` o `/dev/ttyUSB0`; se puede fijar con `SDS011_PORT` en `config/sensores.env`.


## V7.2 · MG811 CO₂ e historial con scroll

- ESP32 esperado en `192.168.137.200`.
- MG811/OKY3352: AOUT mediante divisor 100 kΩ/100 kΩ hacia **GPIO35**; alimentación externa de 6 V y tierra común.
- El endpoint ESP32 `/sensores` incluye el objeto `mg811`; `/co2` expone el detalle del sensor.
- SALUD AMBIENTAL muestra `co2` en ppm solo cuando el firmware entrega una estimación calibrada; sin calibración conserva AOUT/ADC y el estado `SIN_CALIBRAR`.
- El historial tiene scroll vertical propio, cabecera fija y columnas CO₂/MG811 para evitar que la tabla salga del panel.
