<script setup>
defineProps({
  active: { type: String, required: true }
});

const emit = defineEmits(["change"]);
const items = [
  ["dashboard", "Dashboard", "⌂"],
  ["pm25", "PM2.5", "2.5"],
  ["pm10", "PM10", "10"],
  ["aire", "Sensores", "◉"],
  ["historial", "Historial", "▤"],
  ["sistema", "Sistema", "⚙"]
];
</script>

<template>
  <aside class="sidebar">
    <!-- SECCIÓN DE MARCA / LOGO OFICIAL -->
    <div class="brand">
      <img
        class="brand-logo-img"
        src="/Logo.png"
        alt="Logo SIGAIRE"
      />
      <div class="brand-text">
        <strong>SIGAIRE</strong>
        <small>Sistema Inteligente de Gestion Autonoma de la Calidad del Aire</small>
      </div>
    </div>

    <nav class="nav-list" aria-label="Navegación principal">
      <button
        v-for="[key, label, icon] in items"
        :key="key"
        type="button"
        class="nav-button"
        :class="{ active: active === key }"
        @click="emit('change', key)"
      >
        <span aria-hidden="true">{{ icon }}</span>
        {{ label }}
      </button>
    </nav>

    <div class="sidebar-note">
      Raspberry Pi 5
      <span>Sensores + navegación autónoma</span>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  width: 320px;
  height: 100vh;
  padding: 24px 20px;
  background: #ffffff;
  border-right: 2px solid #ead9ec;
  box-shadow: 5px 0 25px rgba(145, 38, 72, 0.05);
  flex-shrink: 0;
}

/* ESTILOS DEL LOGO Y MARCA */
.brand {
  display: flex;
  align-items: center;
  gap: 14px;
  padding-bottom: 22px;
  border-bottom: 2px solid #f0e4ef;
  margin-bottom: 20px;
}

.brand-logo-img {
  width: 52px;
  height: 52px;
  object-fit: contain;
  flex-shrink: 0;
}

.brand-text {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.brand-text strong {
  color: #912648;
  font-size: 20px;
  font-weight: 900;
  letter-spacing: 1px;
}

.brand-text small {
  color: #7a5c7c;
  font-size: 11px;
  font-weight: 700;
  line-height: 1.3;
}

/* LISTA DE NAVEGACIÓN CON LETRAS GRANDES */
.nav-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: 1;
}

.nav-button {
  display: flex;
  align-items: center;
  gap: 16px;
  width: 100%;
  padding: 16px 18px;
  border: none;
  border-radius: 14px;
  background: transparent;
  color: #421e44;
  font-size: 16px;
  font-weight: 800;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s ease;
}

.nav-button:hover {
  background: #fcf1fa;
  color: #b83299;
}

.nav-button.active {
  background: #912648;
  color: #ffffff;
  box-shadow: 0 6px 18px rgba(145, 38, 72, 0.25);
}

.nav-button span {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 28px;
  font-size: 20px;
  text-align: center;
}

.nav-button.active span {
  color: #f7d6e2;
}

/* NOTA INFERIOR */
.sidebar-note {
  margin-top: auto;
  padding: 16px;
  border-radius: 12px;
  background: #fcf5fb;
  border: 1px solid #ead9ec;
  color: #912648;
  font-size: 13px;
  font-weight: 800;
  text-align: center;
}

.sidebar-note span {
  display: block;
  margin-top: 3px;
  color: #7a5c7c;
  font-size: 11px;
  font-weight: 600;
}
</style>