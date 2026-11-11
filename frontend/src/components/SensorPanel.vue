<script setup>
import { computed } from "vue";

const props = defineProps({
  sensors: {
    type: Object,
    default: () => ({})
  }
});

const status = computed(() => props.sensors.esp32_sensor_estado || "SIN_CONEXION");
const connected = computed(() => ["OK", "PARCIAL"].includes(status.value));

function measurement(value, decimals = 2, unit = "") {
  if (value === null || value === undefined || value === "") return "Sin datos";
  const number = Number(value);
  if (!Number.isFinite(number)) return "Sin datos";
  return `${number.toFixed(decimals)}${unit ? ` ${unit}` : ""}`;
}

function label(value) {
  if (!connected.value) return "Sin conexión";
  const statusValue = value || "SIN_DATOS";
  return {
    OK: "Lectura válida",
    LECTURA: "Señal recibida",
    SIN_DATOS: "Sin datos",
    REVISION_ADC: "Revisar ADC",
    SIN_CALIBRAR: "Sin calibrar",
    FUERA_RANGO: "Fuera de rango",
    ESTIMACION_VALIDADA_3_PUNTOS: "Estimación validada",
    ESTIMACION_PENDIENTE_VALIDACION: "Pendiente de validación"
  }[statusValue] || statusValue;
}

function statusType(value) {
  if (!connected.value || value === "SIN_DATOS") return "sensor-state-offline";
  if (["REVISION_ADC", "SIN_CALIBRAR", "FUERA_RANGO", "ESTIMACION_PENDIENTE_VALIDACION"].includes(value)) return "sensor-state-warning";
  return "sensor-state-ok";
}
</script>

<template>
  <section class="panel sensor-monitor-panel">
    <div class="section-heading">
      <div>
        <span class="eyebrow">Sistema Inteligente de Gestión Autonoma de la Calidad del Aire</span>
        <h2>Sensores ambientales de MeteoBot</h2>
      </div>
      <div class="sensor-link-status" :class="connected ? 'sensor-state-ok' : 'sensor-state-offline'">
        <span class="sensor-pulse-dot"></span>
        {{ connected ? `Comunicación activa · ${status}` : "ESP32 sin telemetría reciente" }}
      </div>
    </div>

    <div class="sensor-live-grid">
      <article class="sensor-detail-card">
        <div class="sensor-card-top">
          <div>
            <span class="eyebrow">Temperatura y humedad</span>
            <h3>SHT3x</h3>
          </div>
          <span class="sensor-state" :class="statusType(sensors.sht3x_estado)">
            {{ label(sensors.sht3x_estado) }}
          </span>
        </div>
        <div class="sensor-values-two">
          <div>
            <span>Temperatura</span>
            <strong>{{ measurement(sensors.temperatura, 2, "°C") }}</strong>
          </div>
          <div>
            <span>Humedad relativa</span>
            <strong>{{ measurement(sensors.humedad, 2, "%") }}</strong>
          </div>
        </div>
        <p class="sensor-helper">Medición ambiental obtenida por I²C desde el ESP32.</p>
      </article>

      <article class="sensor-detail-card">
        <div class="sensor-card-top">
          <div>
            <span class="eyebrow">Sensor óptico</span>
            <h3>Sharp · Polvo</h3>
          </div>
          <span class="sensor-state" :class="statusType(sensors.sharp_estado)">
            {{ label(sensors.sharp_estado) }}
          </span>
        </div>
        <div class="sensor-readout">
          <span>Voltaje de salida estimado (Vo)</span>
          <strong>{{ measurement(sensors.sharp_vo_v, 4, "V") }}</strong>
        </div>
        <div class="sensor-secondary-readouts">
          <span>ADC: <b>{{ measurement(sensors.sharp_adc_mv, 1, "mV") }}</b></span>
          <span>RAW: <b>{{ measurement(sensors.sharp_raw, 1) }}</b></span>
        </div>
        <p class="sensor-helper">Señal eléctrica. No equivale a PM2.5/PM10 sin calibración; esos datos provienen del SDS011.</p>
      </article>

      <article class="sensor-detail-card">
        <div class="sensor-card-top">
          <div>
            <span class="eyebrow">Salida analógica y digital</span>
            <h3>BFS-302 · Humo/gas</h3>
          </div>
          <span class="sensor-state" :class="statusType(sensors.bfs302_estado)">
            {{ label(sensors.bfs302_estado) }}
          </span>
        </div>
        <div class="sensor-readout">
          <span>Salida analógica estimada (AOUT)</span>
          <strong>{{ measurement(sensors.bfs302_aout_v, 3, "V") }}</strong>
        </div>
        <div class="sensor-secondary-readouts">
          <span>ADC: <b>{{ measurement(sensors.bfs302_adc_mv, 1, "mV") }}</b></span>
          <span>RAW: <b>{{ measurement(sensors.bfs302_raw, 1) }}</b></span>
          <span>DOUT: <b>{{ sensors.bfs302_dout === 0 || sensors.bfs302_dout === 1 ? sensors.bfs302_dout : "Sin datos" }}</b></span>
        </div>
        <p class="sensor-helper">DOUT es el estado del comparador; LOW no garantiza aire limpio. Validar polaridad y umbral del módulo.</p>
      </article>


      <article class="sensor-detail-card">
        <div class="sensor-card-top">
          <div>
            <span class="eyebrow">Dióxido de carbono</span>
            <h3>MG811 · GPIO35</h3>
          </div>
          <span class="sensor-state" :class="statusType(sensors.mg811_estado)">
            {{ label(sensors.mg811_estado) }}
          </span>
        </div>
        <div class="sensor-readout">
          <span>CO₂ estimado</span>
          <strong>{{ measurement(sensors.co2, 1, "ppm") }}</strong>
        </div>
        <div class="sensor-secondary-readouts">
          <span>AOUT: <b>{{ measurement(sensors.mg811_aout_v, 4, "V") }}</b></span>
          <span>ADC: <b>{{ measurement(sensors.mg811_adc_mv, 2, "mV") }}</b></span>
          <span>RAW: <b>{{ measurement(sensors.mg811_raw, 1) }}</b></span>
          <span>Calibrado: <b>{{ sensors.mg811_calibrado ? "Sí" : "No" }}</b></span>
          <span>Estable 10 min: <b>{{ sensors.mg811_estable_10min ? "Sí" : "No" }}</b></span>
        </div>
        <p class="sensor-helper">Las ppm solo aparecen cuando el firmware dispone de C1/C2 válidos. Sin calibración se conserva AOUT/ADC como señal eléctrica real.</p>
      </article>
    </div>

    <div class="sensor-monitor-footer">
      <span>Última recepción: {{ connected ? measurement(sensors.esp32_sensor_edad_s, 1, "s atrás") : "sin señal" }}</span>
      <span>MG811: {{ sensors.mg811_estado || "SIN_DATOS" }} · Presión: pendiente</span>
      <span>Datos publicados por Raspberry Pi mediante /api/sensores/esp32</span>
    </div>
  </section>
</template>
