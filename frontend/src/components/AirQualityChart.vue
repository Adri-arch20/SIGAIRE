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
    .filter(
      (item) =>
        item.sensores?.pm25 !== null &&
        item.sensores?.pm25 !== undefined &&
        item.sensores?.pm10 !== null &&
        item.sensores?.pm10 !== undefined
    )
    .slice(0, 120)
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

  const pm25 = ordered.map((item) =>
    Number(item.sensores?.pm25 ?? 0)
  );

  const pm10 = ordered.map((item) =>
    Number(item.sensores?.pm10 ?? 0)
  );

  if (chart) chart.destroy();

  chart = new Chart(canvas.value, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "PM2.5",
          data: pm25,
          tension: 0.25,
          pointRadius: 1.5,
          borderColor: "#a60049",
          backgroundColor: "#a60049"
        },
        {
          label: "PM10",
          data: pm10,
          tension: 0.25,
          pointRadius: 1.5,
          borderColor: "#d44184",
          backgroundColor: "#d44184"
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
        <span class="eyebrow">Histórico SDS011</span>
        <h2>PM2.5 y PM10</h2>
      </div>

      <span class="chip secondary">
        Últimas 120 muestras
      </span>
    </div>

    <div class="chart-wrap air-chart-wrap">
      <canvas ref="canvas"></canvas>
    </div>
  </section>
</template>
