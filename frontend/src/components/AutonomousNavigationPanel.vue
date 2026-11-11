<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({
  state: {
    type: Object,
    required: true
  }
});

const previewMode = ref("AUTO");
const previewMovement = ref("STOP");

const vision = computed(() => props.state.vision || {});
const route = computed(() => props.state.ruta || props.state.extra?.ruta || {});
const motors = computed(
  () => props.state.motores_visual || props.state.extra?.motores_visual || {}
);
const yolo = computed(() => props.state.yolo || props.state.extra?.yolo || {});
const esp32Feedback = computed(() =>
  props.state.sensores?.esp32_movimiento !== undefined &&
  props.state.sensores?.esp32_movimiento !== null
);

const movement = computed(() => {
  if (previewMode.value === "VISUAL") return previewMovement.value;
  return props.state.movimiento || "STOP";
});

const motorLeft = computed(() => Number(motors.value.izquierdo || 0));
const motorRight = computed(() => Number(motors.value.derecho || 0));
const motorMax = computed(() => Math.max(1, Number(motors.value.maximo || 255)));

const leftPct = computed(() => Math.min(100, Math.abs(motorLeft.value) / motorMax.value * 100));
const rightPct = computed(() => Math.min(100, Math.abs(motorRight.value) / motorMax.value * 100));

const routeConfidence = computed(() => {
  const n = Number(route.value.confianza || 0);
  return Number.isFinite(n) ? Math.max(0, Math.min(1, n)) : 0;
});

const deviation = computed(() => Number(route.value.desvio_px || 0));
const robotOffset = computed(() => {
  const normalized = Math.max(-1, Math.min(1, deviation.value / 170));
  return normalized * 34;
});

function pct(value) {
  const n = Number(value ?? 0);
  return Number.isFinite(n) ? n.toFixed(1) : "0.0";
}

function riskClass(value) {
  const n = Number(value ?? 0);
  if (n >= 25) return "risk-high";
  if (n >= 10) return "risk-medium";
  return "risk-low";
}

function setPreview(value) {
  previewMode.value = "VISUAL";
  previewMovement.value = value;
}

function followTelemetry() {
  previewMode.value = "AUTO";
}

function handleKey(event) {
  const tag = String(event.target?.tagName || "").toLowerCase();
  if (["input", "select", "textarea"].includes(tag)) return;

  const map = {
    ArrowUp: "AVANZAR",
    w: "AVANZAR",
    W: "AVANZAR",
    ArrowLeft: "IZQUIERDA",
    a: "IZQUIERDA",
    A: "IZQUIERDA",
    ArrowRight: "DERECHA",
    d: "DERECHA",
    D: "DERECHA",
    ArrowDown: "STOP",
    s: "STOP",
    S: "STOP",
    " ": "STOP"
  };

  if (map[event.key]) {
    event.preventDefault();
    setPreview(map[event.key]);
  }

  if (event.key === "Escape") {
    followTelemetry();
  }
}

watch(
  () => props.state.movimiento,
  () => {
    if (previewMode.value === "AUTO") {
      previewMovement.value = props.state.movimiento || "STOP";
    }
  },
  { immediate: true }
);

onMounted(() => window.addEventListener("keydown", handleKey));
onBeforeUnmount(() => window.removeEventListener("keydown", handleKey));
</script>

<template>
  <section class="panel autonomous-panel">
    <div class="section-heading">
      <div>
        <span class="eyebrow">Navegación autónoma</span>
        <h2>YOLO + seguimiento de bordes amarillos</h2>
      </div>
      <div class="autonomous-badges">
        <span class="chip">{{ state.movimiento || "STOP" }}</span>
        <span class="chip secondary">
          YOLO {{ yolo.activo ? "ACTIVO" : "NO DISPONIBLE" }}
        </span>
      </div>
    </div>

    <div class="autonomous-layout">
      <div class="route-visual-card">
        <div class="route-scene">
          <div class="route-border route-border-left"></div>
          <div class="route-border route-border-right"></div>
          <div class="route-centerline"></div>
          <div
            class="route-robot"
            :class="`move-${movement.toLowerCase()}`"
            :style="{ transform: `translateX(${robotOffset}px)` }"
          >
            <span>▲</span>
            <small>MeteoBot</small>
          </div>
        </div>

        <div class="route-summary">
          <div>
            <span>Estado de ruta</span>
            <strong>{{ route.estado || "SIN DATOS" }}</strong>
          </div>
          <div>
            <span>Desvío</span>
            <strong>{{ deviation.toFixed(0) }} px</strong>
          </div>
          <div>
            <span>Confianza</span>
            <strong>{{ (routeConfidence * 100).toFixed(0) }}%</strong>
          </div>
          <div>
            <span>Decisión</span>
            <strong>{{ route.motivo_control || "—" }}</strong>
          </div>
        </div>
      </div>

      <div class="navigation-side-stack">
        <div class="navigation-grid compact-grid">
          <article
            v-for="item in [
              ['Izquierda', vision.izquierda],
              ['Centro', vision.centro],
              ['Derecha', vision.derecha]
            ]"
            :key="item[0]"
            class="zone-card"
          >
            <span>Ocupación {{ item[0] }}</span>
            <strong>{{ pct(item[1]) }}%</strong>
            <div class="progress-track">
              <div
                class="progress-fill"
                :class="riskClass(item[1])"
                :style="{ width: `${Math.min(100, Math.max(0, Number(item[1] || 0)))}%` }"
              ></div>
            </div>
          </article>
        </div>

        <div class="obstacle-card">
          <div>
            <span class="eyebrow">Objeto YOLO</span>
            <strong>{{ vision.objeto || "Sin obstáculo relevante" }}</strong>
          </div>
          <div>
            <span class="eyebrow">Confianza</span>
            <strong>{{ pct(Number(vision.confianza || 0) * 100) }}%</strong>
          </div>
          <div>
            <span class="eyebrow">Imagen original</span>
            <strong>Brillo {{ Number(vision.brillo || 0).toFixed(0) }}</strong>
            <small>Nitidez {{ Number(vision.blur || 0).toFixed(0) }}</small>
          </div>
        </div>
      </div>
    </div>

    <div class="motor-visual-section">
      <div class="motor-visual-heading">
        <div>
          <span class="eyebrow">Apoyo visual</span>
          <h3>{{ esp32Feedback ? "PWM aplicado por el ESP32" : "Salida estimada de motores" }}</h3>
        </div>
        <span class="motor-note">{{ esp32Feedback ? "Lectura de los PWM ordenados al puente H, no RPM medidas." : "Telemetría visual; estos controles no mandan órdenes al ESP32." }}</span>
      </div>

      <div class="motor-bars">
        <div class="motor-meter">
          <div class="motor-meter-label">
            <span>Motor izquierdo</span>
            <strong>{{ motorLeft }}</strong>
          </div>
          <div class="motor-track">
            <div class="motor-fill" :style="{ width: `${leftPct}%` }"></div>
          </div>
        </div>

        <div class="motor-meter">
          <div class="motor-meter-label">
            <span>Motor derecho</span>
            <strong>{{ motorRight }}</strong>
          </div>
          <div class="motor-track">
            <div class="motor-fill" :style="{ width: `${rightPct}%` }"></div>
          </div>
        </div>
      </div>
    </div>

    <div class="interactive-movement">
      <div class="interactive-copy">
        <span class="eyebrow">Vista interactiva</span>
        <h3>Previsualiza los movimientos</h3>
        <p>
          Usa los botones o WASD/flechas para animar la vista. Presiona Esc para volver a seguir la telemetría real.
        </p>
      </div>

      <div class="movement-pad" aria-label="Simulador visual de movimiento">
        <button type="button" class="pad-up" @click="setPreview('AVANZAR')">↑</button>
        <button type="button" class="pad-left" @click="setPreview('IZQUIERDA')">←</button>
        <button type="button" class="pad-stop" @click="setPreview('STOP')">STOP</button>
        <button type="button" class="pad-right" @click="setPreview('DERECHA')">→</button>
        <button type="button" class="pad-auto" :class="{ active: previewMode === 'AUTO' }" @click="followTelemetry">
          AUTO
        </button>
      </div>

      <div class="preview-state">
        <span>Vista actual</span>
        <strong>{{ movement }}</strong>
        <small>{{ previewMode === "AUTO" ? "Siguiendo al robot" : "Simulación local" }}</small>
      </div>
    </div>
  </section>
</template>
