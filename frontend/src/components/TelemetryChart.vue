<script setup>
import { Chart } from "chart.js/auto";
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({
  records: {
    type: Array,
    default: () => []
  }
});

const canvas = ref(null);
let chart = null;

function render() {
  if (!canvas.value) return;

  const ordered = [...props.records]
    .slice(0, 60)
    .reverse();

  const labels = ordered.map((item) => {
    const date = new Date(item.timestamp);
    return Number.isNaN(date.getTime())
      ? item.timestamp
      : date.toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit"
        });
  });

  const left = ordered.map((item) => Number(item.vision?.izquierda || 0));
  const center = ordered.map((item) => Number(item.vision?.centro || 0));
  const right = ordered.map((item) => Number(item.vision?.derecha || 0));

  if (chart) {
    chart.destroy();
  }

  chart = new Chart(canvas.value, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Izquierda",
          data: left,
          tension: 0.25,
          pointRadius: 1.5,
          borderColor: "#c21a65",
          backgroundColor: "#c21a65"
        },
        {
          label: "Centro",
          data: center,
          tension: 0.25,
          pointRadius: 1.5,
          borderColor: "#a60049",
          backgroundColor: "#a60049"
        },
        {
          label: "Derecha",
          data: right,
          tension: 0.25,
          pointRadius: 1.5,
          borderColor: "#ef8fba",
          backgroundColor: "#ef8fba"
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
      scales: {
        y: {
          beginAtZero: true,
          suggestedMax: 100,
          title: {
            display: true,
            text: "Ocupación (%)"
          }
        }
      }
    }
  });
}

onMounted(async () => {
  await nextTick();
  render();
});

watch(
  () => props.records,
  async () => {
    await nextTick();
    render();
  },
  { deep: true }
);

onBeforeUnmount(() => {
  if (chart) chart.destroy();
});
</script>

<template>
  <section class="panel">
    <div class="section-heading">
      <div>
        <span class="eyebrow">Visualización histórica</span>
        <h2>Ocupación detectada</h2>
      </div>
      <span class="chip secondary">Últimas 60 muestras</span>
    </div>

    <div class="chart-wrap">
      <canvas ref="canvas"></canvas>
    </div>
  </section>
</template>
