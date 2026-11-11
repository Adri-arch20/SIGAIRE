<script setup>
import { Chart } from "chart.js/auto";
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch
} from "vue";

const props = defineProps({
  metric: {
    type: String,
    required: true
  },
  sensors: {
    type: Object,
    default: () => ({})
  },
  records: {
    type: Array,
    default: () => []
  },
  stats: {
    type: Object,
    default: () => ({})
  }
});

const canvas = ref(null);
let chart = null;

const isPm25 = computed(() => props.metric === "pm25");
const title = computed(() => isPm25.value ? "PM2.5" : "PM10");
const rawKey = computed(() => `${props.metric}_raw`);
const filteredKey = computed(() => `${props.metric}_filtered`);
const stdKey = computed(() => `${props.metric}_std`);
const minKey = computed(() => `${props.metric}_min`);
const maxKey = computed(() => `${props.metric}_max`);

const storedRecords = computed(() =>
  props.records.filter((item) => {
    const value = item.sensores?.[props.metric];
    return value !== null && value !== undefined;
  })
);

const latestStored = computed(() => storedRecords.value[0] || null);

function number(value, digits = 1) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toFixed(digits) : "—";
}

function timeLabel(timestamp) {
  if (!timestamp) return "—";

  const date = new Date(timestamp);

  return Number.isNaN(date.getTime())
    ? timestamp
    : date.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
      });
}

function fullTime(timestamp) {
  if (!timestamp) return "—";

  const date = new Date(timestamp);

  return Number.isNaN(date.getTime())
    ? timestamp
    : date.toLocaleString();
}

function renderChart() {
  if (!canvas.value) return;

  const ordered = [...storedRecords.value]
    .slice(0, 240)
    .reverse();

  const labels = ordered.map((item) =>
    timeLabel(item.timestamp)
  );

  const finalData = ordered.map((item) =>
    Number(item.sensores?.[props.metric] ?? 0)
  );

  const filteredData = ordered.map((item) => {
    const value = item.sensores?.[filteredKey.value];
    return value === null || value === undefined ? null : Number(value);
  });

  const rawData = ordered.map((item) => {
    const value = item.sensores?.[rawKey.value];
    return value === null || value === undefined ? null : Number(value);
  });

  if (chart) {
    chart.destroy();
  }

  chart = new Chart(canvas.value, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: `${title.value} final`,
          data: finalData,
          tension: 0.22,
          pointRadius: 0,
          borderWidth: 2.5,
          borderColor: "#a60049",
          backgroundColor: "#a60049"
        },
        {
          label: `${title.value} filtrado`,
          data: filteredData,
          tension: 0.22,
          pointRadius: 0,
          borderWidth: 1.5,
          borderDash: [6, 4],
          borderColor: "#d44184",
          backgroundColor: "#d44184"
        },
        {
          label: `${title.value} crudo`,
          data: rawData,
          tension: 0.15,
          pointRadius: 0,
          borderWidth: 1,
          borderColor: "#f1afcc",
          backgroundColor: "#f1afcc"
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: {
        mode: "index",
        intersect: false
      },
      plugins: {
        legend: {
          position: "bottom"
        }
      },
      scales: {
        x: {
          ticks: {
            maxTicksLimit: 10
          }
        },
        y: {
          beginAtZero: true,
          title: {
            display: true,
            text: "µg/m³"
          }
        }
      }
    }
  });
}

onMounted(async () => {
  await nextTick();
  renderChart();
});

watch(
  () => [
    props.metric,
    props.records
  ],
  async () => {
    await nextTick();
    renderChart();
  },
  {
    deep: true
  }
);

onBeforeUnmount(() => {
  if (chart) chart.destroy();
});
</script>

<template>
  <section class="particle-dashboard">
    <div class="particle-dashboard-title">
      <div>
        <span class="eyebrow">Dashboard individual SDS011</span>
        <h2>{{ title }} · tiempo real + histórico guardado</h2>
      </div>

      <div class="particle-badges">
        <span
          class="chip"
          :class="sensors.sds011_estado === 'OK' ? 'air-status-ok' : 'air-status-warm'"
        >
          {{ sensors.sds011_estado || "SIN_DATOS" }}
        </span>

        <span class="chip secondary">
          Calibración: {{ sensors.sds011_calibracion || "FABRICA" }}
        </span>
      </div>
    </div>

    <div class="particle-live-grid">
      <article class="panel particle-primary-card">
        <span class="eyebrow">{{ title }} final</span>

        <div class="particle-big-value">
          <strong>{{ number(sensors[metric]) }}</strong>
          <span>µg/m³</span>
        </div>

        <p>
          Valor usado por SIGAIRE después de validación de trama,
          filtro robusto, suavizado EMA y coeficientes de calibración.
        </p>
      </article>

      <article class="panel particle-detail-card">
        <span>Lectura cruda</span>
        <strong>{{ number(sensors[rawKey]) }} µg/m³</strong>
        <small>Último dato recibido directamente del SDS011.</small>
      </article>

      <article class="panel particle-detail-card">
        <span>Lectura filtrada</span>
        <strong>{{ number(sensors[filteredKey]) }} µg/m³</strong>
        <small>Antes de aplicar pendiente e intercepto de calibración.</small>
      </article>

      <article class="panel particle-detail-card">
        <span>Variación de ventana</span>
        <strong>± {{ number(sensors[stdKey]) }} µg/m³</strong>
        <small>
          Rango actual:
          {{ number(sensors[minKey]) }} –
          {{ number(sensors[maxKey]) }} µg/m³
        </small>
      </article>
    </div>

    <section class="panel">
      <div class="section-heading">
        <div>
          <span class="eyebrow">Streaming + SQLite</span>
          <h2>{{ title }} en tiempo real</h2>
        </div>

        <span class="chip secondary">
          {{ storedRecords.length }} puntos cargados
        </span>
      </div>

      <div class="particle-chart-wrap">
        <canvas ref="canvas"></canvas>
      </div>
    </section>

    <section class="panel">
      <div class="section-heading">
        <div>
          <span class="eyebrow">Persistencia local</span>
          <h2>Últimas mediciones guardadas de {{ title }}</h2>
        </div>

        <span class="chip secondary">
          SQLite · {{ stats.records ?? 0 }} registros totales
        </span>
      </div>

      <div class="particle-storage-summary">
        <div>
          <span>Último guardado</span>
          <strong>{{ fullTime(latestStored?.timestamp) }}</strong>
        </div>

        <div>
          <span>Valor guardado</span>
          <strong>
            {{ number(latestStored?.sensores?.[metric]) }} µg/m³
          </strong>
        </div>

        <div>
          <span>Muestras del filtro</span>
          <strong>{{ sensors.sds011_muestras ?? 0 }}</strong>
        </div>

        <div>
          <span>Outliers recientes</span>
          <strong>{{ sensors.sds011_outliers ?? 0 }}</strong>
        </div>
      </div>

      <div class="table-scroll particle-table-scroll">
        <table>
          <thead>
            <tr>
              <th>Hora</th>
              <th>Final</th>
              <th>Filtrado</th>
              <th>Crudo</th>
              <th>σ</th>
            </tr>
          </thead>

          <tbody>
            <tr
              v-for="item in storedRecords.slice(0, 20)"
              :key="item.id || item.timestamp"
            >
              <td>{{ fullTime(item.timestamp) }}</td>
              <td>{{ number(item.sensores?.[metric]) }}</td>
              <td>{{ number(item.sensores?.[filteredKey]) }}</td>
              <td>{{ number(item.sensores?.[rawKey]) }}</td>
              <td>{{ number(item.sensores?.[stdKey]) }}</td>
            </tr>

            <tr v-if="storedRecords.length === 0">
              <td colspan="5">
                Aún no hay datos guardados para {{ title }}.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>
