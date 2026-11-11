# SALUD AMBIENTAL · MeteoBot V7.2

## Cambios principales

- Integración completa del sensor MG811/OKY3352 para CO₂ desde el firmware ESP32 suministrado.
- MG811 en GPIO35 con divisor 100 kΩ / 100 kΩ y alimentación externa de 6 V con GND común.
- El puente Raspberry lee `mg811` dentro de `GET /sensores` del ESP32.
- El backend publica:
  - `co2` en ppm cuando el firmware entrega una estimación calibrada.
  - `mg811_aout_v`, `mg811_adc_mv`, `mg811_raw`.
  - estado de calibración, estabilidad, evento, línea base y validación.
- La vista pública SALUD AMBIENTAL muestra CO₂ y, mientras no esté calibrado, muestra AOUT real sin inventar ppm.
- El panel técnico incluye una tarjeta MG811.
- El historial incorpora columnas CO₂ y MG811 AOUT.
- El historial tiene un scroll interno con cabecera fija para evitar que las filas salgan del panel.
- Exportación CSV ampliada con los campos MG811.
- IP predeterminada del ESP32: `192.168.137.200`.
- Se mantienen SDS011 PM2.5/PM10, SHT3x, Sharp, BFS-302, navegación autónoma y YOLO.

## Firmware ESP32

Archivo:

`robot/esp32_salud_ambiental_v7/esp32_salud_ambiental_v7.ino`

El firmware expone:

- `GET /sensores`
- `GET /co2`
- `GET /estado`
- endpoints de motores ya existentes.

## Ejecución

```bash
cd ~/Downloads/SALUD_AMBIENTAL_MeteoBot_v7
chmod +x scripts/*.sh
./scripts/install_sensores.sh
./scripts/start_salud_ambiental_sensores.sh
```

Para probar solo la interfaz con datos simulados, incluyendo CO₂:

```bash
python3 scripts/test_salud_ambiental.py
```

## Comprobación del MG811

Con el ESP32 en `192.168.137.200`:

```bash
curl http://192.168.137.200/co2
curl http://192.168.137.200/sensores
```

Desde el backend de la Raspberry:

```bash
curl http://127.0.0.1:5000/api/sensores/esp32
curl http://127.0.0.1:5000/api/estado
```

El valor `co2` permanecerá nulo hasta que el firmware tenga referencias de calibración válidas; AOUT/ADC siguen disponibles para diagnóstico.
