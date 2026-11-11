<script setup>
const props = defineProps({
  state: {
    type: Object,
    required: true
  },
  wsConnected: Boolean
});

function statusClass(value) {
  const normalized = String(value || "").toLowerCase();

  if (
    normalized.includes("online") ||
    normalized.includes("conectado") ||
    normalized.includes("avanzar")
  ) {
    return "positive";
  }

  if (
    normalized.includes("stop") ||
    normalized.includes("offline") ||
    normalized.includes("desconectado")
  ) {
    return "danger";
  }

  return "neutral";
}
</script>

<template>
  <section class="status-grid">
    <article class="metric-card">
      <span class="eyebrow">MeteoBot</span>
      <strong :class="statusClass(state.estado)">
        {{ (state.estado || "offline").toUpperCase() }}
      </strong>
      <small>{{ state.modo || "Sin modo" }}</small>
    </article>

    <article class="metric-card">
      <span class="eyebrow">Movimiento</span>
      <strong :class="statusClass(state.movimiento)">
        {{ state.movimiento || "STOP" }}
      </strong>
      <small>Orden actual</small>
    </article>

    <article class="metric-card">
      <span class="eyebrow">Navegación</span>
      <strong>{{ state.gesto || "AUTONOMO" }}</strong>
      <small>YOLO + bordes amarillos</small>
    </article>

    <article class="metric-card">
      <span class="eyebrow">ESP32</span>
      <strong :class="statusClass(state.esp32)">
        {{ state.esp32 || "desconectado" }}
      </strong>
      <small>Control de motores</small>
    </article>

    <article class="metric-card">
      <span class="eyebrow">Tiempo real</span>
      <strong :class="wsConnected ? 'positive' : 'danger'">
        {{ wsConnected ? "CONECTADO" : "RECONECTANDO" }}
      </strong>
      <small>WebSocket</small>
    </article>
  </section>
</template>
