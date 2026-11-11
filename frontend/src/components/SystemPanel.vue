<script setup>
const props = defineProps({
  stats: {
    type: Object,
    default: () => ({})
  }
});

function formatBytes(value) {
  const bytes = Number(value || 0);

  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;

  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}
</script>

<template>
  <section class="panel">
    <div class="section-heading">
      <div>
        <span class="eyebrow">Sistema</span>
        <h2>Raspberry Pi 5 y almacenamiento</h2>
      </div>
      <span class="chip">SQLite local</span>
    </div>

    <div class="system-grid">
      <article>
        <span>Registros</span>
        <strong>{{ stats.records ?? 0 }}</strong>
      </article>

      <article>
        <span>Tamaño de base</span>
        <strong>{{ formatBytes(stats.database_size_bytes) }}</strong>
      </article>

      <article>
        <span>Clientes en tiempo real</span>
        <strong>{{ stats.websocket_clients ?? 0 }}</strong>
      </article>

      <article>
        <span>Intervalo de guardado</span>
        <strong>{{ stats.store_interval_seconds ?? 1 }} s</strong>
      </article>
    </div>

    <div class="system-detail">
      <span class="eyebrow">Base de datos</span>
      <code>{{ stats.database_path || "backend/data/singare.db" }}</code>
    </div>

    <div class="system-detail">
      <span class="eyebrow">Último registro</span>
      <strong>{{ stats.last_record || "Sin datos" }}</strong>
    </div>

    <div class="api-list">
      <h3>API</h3>
      <code>POST /api/telemetria</code>
      <code>GET /api/estado</code>
      <code>GET /api/registros</code>
      <code>DELETE /api/registros/:id</code>
      <code>DELETE /api/registros</code>
      <code>GET /api/registros/export.csv</code>
      <code>WS /ws/telemetria</code>
    </div>
  </section>
</template>
