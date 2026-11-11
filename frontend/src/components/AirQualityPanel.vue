<script setup>
import { computed } from "vue";

const props = defineProps({
  sensors: {
    type: Object,
    default: () => ({})
  }
});

const status = computed(() => props.sensors.sds011_estado || "SIN_DATOS");

function value(v) {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  return Number.isFinite(n) ? n.toFixed(1) : "—";
}

function sigma(v) {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  return Number.isFinite(n) ? `± ${n.toFixed(1)}` : "—";
}

function statusClass() {
  const s = String(status.value).toUpperCase();

  if (s === "OK") return "air-status-ok";
  if (s.includes("CALENT") || s.includes("ESTABIL")) return "air-status-warm";
  return "air-status-error";
}
</script>

<template>
  <section class="panel air-panel">
    <div class="section-heading">
      <div>
        <span class="eyebrow">Nova Fitness SDS011</span>
        <h2>Partículas suspendidas · valor final</h2>
      </div>

      <div class="particle-badges">
        <span
          class="chip"
          :class="statusClass()"
        >
          {{ status }}
        </span>

        <span class="chip secondary">
          {{ sensors.sds011_calibracion || "FABRICA" }}
        </span>
      </div>
    </div>

    <div class="air-main-grid">
      <article class="air-reading">
        <span>PM2.5 final</span>

        <div class="air-value-row">
          <strong>{{ value(sensors.pm25) }}</strong>
          <em>µg/m³</em>
        </div>

        <small>
          Filtrado: {{ value(sensors.pm25_filtered) }} ·
          Crudo: {{ value(sensors.pm25_raw) }} ·
          σ {{ sigma(sensors.pm25_std) }}
        </small>
      </article>

      <article class="air-reading">
        <span>PM10 final</span>

        <div class="air-value-row">
          <strong>{{ value(sensors.pm10) }}</strong>
          <em>µg/m³</em>
        </div>

        <small>
          Filtrado: {{ value(sensors.pm10_filtered) }} ·
          Crudo: {{ value(sensors.pm10_raw) }} ·
          σ {{ sigma(sensors.pm10_std) }}
        </small>
      </article>

      <article class="air-meta-card">
        <span class="eyebrow">Procesamiento SDS011</span>
        <strong>{{ sensors.sds011_muestras ?? 0 }} muestras</strong>
        <small>ID: {{ sensors.sds011_id || "—" }}</small>
        <small>Outliers detectados: {{ sensors.sds011_outliers ?? 0 }}</small>
        <small>
          Mediana/MAD + media recortada + EMA + coeficientes de calibración.
        </small>
      </article>
    </div>
  </section>
</template>
