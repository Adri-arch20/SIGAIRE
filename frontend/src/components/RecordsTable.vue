<script setup>
import { computed, ref } from "vue";

const props = defineProps({
  records: {
    type: Array,
    default: () => []
  },
  busy: Boolean
});

const emit = defineEmits(["delete-record", "delete-all", "refresh"]);

const movementFilter = ref("");

const filtered = computed(() => {
  if (!movementFilter.value) return props.records;

  return props.records.filter(
    (item) => item.movimiento === movementFilter.value
  );
});

function readableDate(value) {
  if (!value) return "—";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return value;

  return date.toLocaleString();
}

function confirmDelete(id) {
  if (window.confirm(`¿Eliminar el registro #${id}?`)) {
    emit("delete-record", id);
  }
}

function confirmDeleteAll() {
  if (
    window.confirm(
      "¿Eliminar TODOS los registros almacenados en la Raspberry Pi? Esta acción no se puede deshacer."
    )
  ) {
    emit("delete-all");
  }
}
</script>

<template>
  <section class="panel records-panel">
    <div class="records-toolbar">
      <div>
        <span class="eyebrow">Historial</span>
        <h2>Registros almacenados</h2>
      </div>

      <div class="toolbar-actions">
        <select v-model="movementFilter" aria-label="Filtrar movimiento">
          <option value="">Todos los movimientos</option>
          <option value="AVANZAR">AVANZAR</option>
          <option value="STOP">STOP</option>
          <option value="IZQUIERDA">IZQUIERDA</option>
          <option value="DERECHA">DERECHA</option>
          <option value="LENTO">LENTO</option>
        </select>

        <a
          class="button secondary-button"
          href="/api/registros/export.csv"
        >
          Exportar CSV
        </a>

        <button
          type="button"
          class="button secondary-button"
          :disabled="busy"
          @click="emit('refresh')"
        >
          Actualizar
        </button>

        <button
          type="button"
          class="button danger-button"
          :disabled="busy || records.length === 0"
          @click="confirmDeleteAll"
        >
          Eliminar todos
        </button>
      </div>
    </div>

    <div class="table-wrap records-table-wrap">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Fecha</th>
            <th>Movimiento</th>
            <th>Navegación</th>
            <th>ESP32</th>
            <th>Centro</th>
            <th>Objeto</th>
            <th>PM2.5</th>
            <th>PM10</th>
            <th>CO₂ (ppm)</th>
            <th>MG811 AOUT (V)</th>
            <th>Temp (°C)</th>
            <th>HR (%)</th>
            <th>Sharp Vo (V)</th>
            <th>BFS AOUT (V)</th>
            <th>BFS DOUT</th>
            <th></th>
          </tr>
        </thead>

        <tbody>
          <tr v-if="filtered.length === 0">
            <td colspan="17" class="empty-cell">
              No hay registros con este filtro.
            </td>
          </tr>

          <tr
            v-for="item in filtered"
            :key="item.id"
          >
            <td>#{{ item.id }}</td>
            <td>{{ readableDate(item.timestamp) }}</td>
            <td>
              <span class="table-chip">
                {{ item.movimiento }}
              </span>
            </td>
            <td>{{ item.gesto || "—" }}</td>
            <td>{{ item.esp32 || "—" }}</td>
            <td>{{ Number(item.vision?.centro || 0).toFixed(1) }}%</td>
            <td>{{ item.vision?.objeto || "—" }}</td>
            <td>{{ item.sensores?.pm25 == null ? "—" : Number(item.sensores.pm25).toFixed(1) }}</td>
            <td>{{ item.sensores?.pm10 == null ? "—" : Number(item.sensores.pm10).toFixed(1) }}</td>
            <td>{{ item.sensores?.co2 == null ? "—" : Number(item.sensores.co2).toFixed(1) }}</td>
            <td>{{ item.sensores?.mg811_aout_v == null ? "—" : Number(item.sensores.mg811_aout_v).toFixed(4) }}</td>
            <td>{{ item.sensores?.temperatura == null ? "—" : Number(item.sensores.temperatura).toFixed(2) }}</td>
            <td>{{ item.sensores?.humedad == null ? "—" : Number(item.sensores.humedad).toFixed(2) }}</td>
            <td>{{ item.sensores?.sharp_vo_v == null ? "—" : Number(item.sensores.sharp_vo_v).toFixed(4) }}</td>
            <td>{{ item.sensores?.bfs302_aout_v == null ? "—" : Number(item.sensores.bfs302_aout_v).toFixed(3) }}</td>
            <td>{{ item.sensores?.bfs302_dout ?? "—" }}</td>
            <td>
              <button
                type="button"
                class="icon-button"
                :disabled="busy"
                :aria-label="`Eliminar registro ${item.id}`"
                @click="confirmDelete(item.id)"
              >
                ×
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
