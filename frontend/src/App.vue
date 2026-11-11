<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import EnvironmentalHealthView from "./components/EnvironmentalHealthView.vue";
import Sidebar from "./components/Sidebar.vue";
import StatusCards from "./components/StatusCards.vue";
import AutonomousNavigationPanel from "./components/AutonomousNavigationPanel.vue";
import AirQualityPanel from "./components/AirQualityPanel.vue";
import AirQualityChart from "./components/AirQualityChart.vue";
import ParticleDashboard from "./components/ParticleDashboard.vue";
import SensorPanel from "./components/SensorPanel.vue";
import TelemetryChart from "./components/TelemetryChart.vue";
import RecordsTable from "./components/RecordsTable.vue";
import SystemPanel from "./components/SystemPanel.vue";

import { deleteJSON, getJSON, websocketUrl } from "./api";

const loadingSplash = ref(true);
const isAdminView = ref(false);
const active = ref("dashboard");
const wsConnected = ref(false);
const busy = ref(false);
const errorMessage = ref("");

const current = ref({
  robot: "MeteoBot",
  estado: "offline",
  modo: "",
  movimiento: "STOP",
  gesto: "AUTONOMO",
  esp32: "desconectado",
  vision: { izquierda: 0, centro: 0, derecha: 0, objeto: "", confianza: 0, brillo: 0, blur: 0 },
  ruta: { estado: "SIN_DATOS", motivo_control: "ESPERANDO_TELEMETRIA", confianza: 0, desvio_px: 0 },
  motores_visual: { izquierdo: 0, derecho: 0, maximo: 255 },
  yolo: { activo: false, requerido: true, modelo: "", obstaculo: false },
  sensores: {
    pm25: null, pm10: null, pm25_raw: null, pm10_raw: null,
    pm25_filtered: null, pm10_filtered: null, pm25_std: null, pm10_std: null,
    pm25_min: null, pm25_max: null, pm10_min: null, pm10_max: null,
    sds011_estado: "SIN_DATOS", sds011_calibracion: "FABRICA", sds011_muestras: 0,
    sds011_id: "", sds011_outliers: 0,
    co2: null, temperatura: null, humedad: null, presion: null,
    esp32_sensor_estado: "SIN_CONEXION", esp32_sensor_edad_s: null,
    sht3x_estado: "SIN_DATOS",
    sharp_estado: "SIN_DATOS", sharp_vo_v: null, sharp_adc_mv: null, sharp_raw: null,
    sharp_raw_min: null, sharp_raw_max: null, sharp_adc_alto: null,
    bfs302_estado: "SIN_DATOS", bfs302_aout_v: null, bfs302_adc_mv: null,
    bfs302_raw: null, bfs302_dout: null,
    mg811_estado: "SIN_DATOS", mg811_aout_v: null, mg811_adc_mv: null, mg811_raw: null,
    mg811_calibrado: false, mg811_estable_10min: false, mg811_deriva_10min_mv: null,
    mg811_rango_10min_mv: null, mg811_linea_base_adc_mv: null, mg811_delta_aout_mv: null,
    mg811_evento_senal: null, mg811_listo_para_referencia: false,
    mg811_ppm_validado_tercer_punto: false, mg811_error_validacion_pct: null,
    mg811_metodo_ppm: null
  }
});

const records = ref([]);
const stats = ref({});

// Reproducción histórica: solo se utiliza cuando el WebSocket real está desconectado.
const demoRecords = ref([]);
const demoIndex = ref(-1);
const demoPaused = ref(false);
let demoTimer = null;

// wsConnected indica la conexión navegador-servidor; aquí también se comprueba el ESP32.
const robotOnline = computed(() => {
  if (!wsConnected.value) return false;
  const statusValues = [
    current.value?.esp32,
    current.value?.sensores?.esp32_sensor_estado,
    current.value?.estado
  ].filter((value) => value !== null && value !== undefined && value !== "");
  const normalized = statusValues.map((value) => String(value).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase());
  const disconnected = normalized.some((value) => /desconect|offline|sin[_ ]conexion|sin[_ ]datos|timeout/.test(value));
  const connected = normalized.some((value) => /conectado|connected|online|activo|active|\bok\b|lectura/.test(value));
  return connected && !disconnected;
});

const demoModeActive = computed(() => !robotOnline.value && demoRecords.value.length > 0 && demoIndex.value >= 0);
const displayState = computed(() => robotOnline.value ? current.value : (demoRecords.value[demoIndex.value] || current.value));
const displayRecords = computed(() => (!robotOnline.value && demoRecords.value.length) ? [...demoRecords.value].reverse() : records.value);
const displayLastUpdate = computed(() => {
  if (demoModeActive.value) {
    const value = demoRecords.value[demoIndex.value]?.timestamp;
    const date = value ? new Date(value) : null;
    return date && !Number.isNaN(date.getTime())
      ? `Registro histórico: ${date.toLocaleString("es-MX")}`
      : "Reproduciendo datos históricos";
  }
  return lastUpdate.value;
});
const demoProgress = computed(() => demoRecords.value.length ? `${Math.max(0, demoIndex.value + 1)} / ${demoRecords.value.length}` : "0 / 0");
let socket = null;
let reconnectTimer = null;
let statsTimer = null;
let recordsTimer = null;
let stateTimer = null;

const lastUpdate = computed(() => {
  const value = current.value.timestamp;
  if (!value) return "Esperando telemetría...";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
});

async function loadInitial() {
  try { current.value = await getJSON("/api/estado"); } catch { /* estado offline */ }
  await Promise.all([loadRecords(), loadStats()]);
}

async function loadRecords() {
  try {
    const data = await getJSON("/api/registros?limit=360");
    records.value = data.items || [];
  } catch (error) {
    errorMessage.value = `No se pudo cargar el historial: ${error.message}`;
  }
}

async function loadStats() {
  try { stats.value = await getJSON("/api/estadisticas"); }
  catch (error) { errorMessage.value = `No se pudieron cargar estadísticas: ${error.message}`; }
}

function parseDemoTimestamp(value) {
  const match = String(value || "").trim().match(/^(\d{1,2})\/(\d{1,2})\/(\d{4}),\s*(\d{1,2}):(\d{2}):(\d{2})\s*([ap])\.m\.$/i);
  if (!match) return null;
  const [, day, month, year, rawHour, minute, second, period] = match;
  let hour = Number(rawHour) % 12;
  if (period.toLowerCase() === "p") hour += 12;
  const date = new Date(Number(year), Number(month) - 1, Number(day), hour, Number(minute), Number(second));
  if (Number.isNaN(date.getTime())) return null;
  const pad = (n) => String(n).padStart(2, "0");
  // Fecha local sin sufijo Z para conservar la hora que aparece en el CSV.
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function demoNumber(value) {
  const clean = String(value ?? "").trim();
  if (!clean || clean === "—" || clean === "×") return null;
  const parsed = Number(clean.replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
}

async function loadDemoHistory() {
  try {
    // Archivo estático local. No sustituye ni modifica las rutas /api existentes.
    const response = await fetch("/data/historial_sigaire.tsv", { cache: "no-cache" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const raw = await response.text();
    const lines = raw.replace(/^\uFEFF/, "").split(/\r?\n/).filter((line) => line.trim());
    if (lines.length < 2) throw new Error("El archivo no contiene registros.");

    const headers = lines.shift().split("\t");
    const column = (name) => headers.indexOf(name);
    const parsed = [];

    for (const line of lines) {
      const row = line.split("\t");
      const timestamp = parseDemoTimestamp(row[column("Fecha")]);
      if (!timestamp) continue;

      const sensors = {
        pm25: demoNumber(row[column("PM2.5")]),
        pm10: demoNumber(row[column("PM10")]),
        co2: null, // El CSV no contiene una concentración de CO₂ validada.
        mg811_aout_v: demoNumber(row[column("MG811 AOUT (V)")]),
        temperatura: demoNumber(row[column("Temp (°C)")]),
        humedad: demoNumber(row[column("HR (%)")]),
        sharp_vo_v: demoNumber(row[column("Sharp Vo (V)")]),
        bfs302_aout_v: demoNumber(row[column("BFS AOUT (V)")]),
        bfs302_dout: demoNumber(row[column("BFS DOUT")]),
        sds011_estado: "HISTORICO",
        sht3x_estado: "HISTORICO",
        mg811_estado: "HISTORICO",
        sharp_estado: "HISTORICO",
        bfs302_estado: "HISTORICO",
        esp32_sensor_estado: "REGISTRO HISTORICO"
      };

      parsed.push({
        id: row[column("ID")] || `demo-${parsed.length + 1}`,
        timestamp,
        fecha: row[column("Fecha")],
        movimiento: row[column("Movimiento")],
        navegacion: row[column("Navegación")],
        esp32_registro: row[column("ESP32")],
        robot: "MeteoBot",
        estado: "historico",
        modo: "DEMOSTRACION",
        stored: true,
        sensores: sensors
      });
    }

    // El archivo original está ordenado del registro más reciente al más antiguo.
    // Se invierte para reproducirlo cronológicamente.
    demoRecords.value = parsed.reverse();
    if (!demoRecords.value.length) throw new Error("No se pudieron interpretar las fechas del historial.");
    demoIndex.value = 0;
  } catch (error) {
    console.error("No se pudo cargar el historial de demostración:", error);
    errorMessage.value = `No se pudo cargar el historial de demostración: ${error.message}`;
  }
}

function stopDemoReplay() {
  if (demoTimer) clearInterval(demoTimer);
  demoTimer = null;
  demoPaused.value = false;
}

function startDemoReplay() {
  if (robotOnline.value || !demoRecords.value.length || demoTimer) return;
  if (demoIndex.value < 0 || demoIndex.value >= demoRecords.value.length) demoIndex.value = 0;
  demoPaused.value = false;
  demoTimer = setInterval(() => {
    if (demoPaused.value || robotOnline.value) return;
    demoIndex.value = (demoIndex.value + 1) % demoRecords.value.length;
  }, 3000);
}

function restartDemoReplay() {
  if (!demoRecords.value.length || robotOnline.value) return;
  demoIndex.value = 0;
  demoPaused.value = false;
  if (!demoTimer) startDemoReplay();
}

function scheduleReconnect() {
  clearTimeout(reconnectTimer);
  reconnectTimer = setTimeout(connectWebSocket, 2000);
}

function connectWebSocket() {
  if (socket) {
    socket.onopen = null; socket.onclose = null; socket.onerror = null; socket.onmessage = null;
    try { socket.close(); } catch { /* sin acción */ }
  }

  socket = new WebSocket(websocketUrl());
  socket.onopen = () => {
    wsConnected.value = true;
    if (robotOnline.value) stopDemoReplay(); else startDemoReplay();
    errorMessage.value = "";
  };
  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      current.value = data;
      if (robotOnline.value) stopDemoReplay(); else startDemoReplay();
      if (data.stored && data.id) {
        const withoutDuplicate = records.value.filter((item) => item.id !== data.id);
        records.value = [data, ...withoutDuplicate].slice(0, 360);
      }
    } catch { errorMessage.value = "Se recibió telemetría inválida."; }
  };
  socket.onclose = () => { wsConnected.value = false; startDemoReplay(); scheduleReconnect(); };
  socket.onerror = () => { wsConnected.value = false; startDemoReplay(); };
}

async function removeRecord(id) {
  busy.value = true;
  try {
    await deleteJSON(`/api/registros/${id}`);
    await Promise.all([loadRecords(), loadStats()]);
  } catch (error) { errorMessage.value = `No se pudo eliminar el registro: ${error.message}`; }
  finally { busy.value = false; }
}

async function removeAll() {
  busy.value = true;
  try {
    await deleteJSON("/api/registros");
    records.value = [];
    await loadStats();
  } catch (error) { errorMessage.value = `No se pudieron eliminar los registros: ${error.message}`; }
  finally { busy.value = false; }
}

onMounted(async () => {
  setTimeout(() => { loadingSplash.value = false; }, 1450);
  await loadInitial();
  await loadDemoHistory();
  connectWebSocket();
  statsTimer = setInterval(loadStats, 10000);
  stateTimer = setInterval(async () => {
    try {
      current.value = await getJSON("/api/estado");
      if (robotOnline.value) stopDemoReplay(); else startDemoReplay();
    } catch { /* WS reintenta */ }
  }, 3000);
  recordsTimer = setInterval(() => { if (active.value === "historial") loadRecords(); }, 10000);
});

onBeforeUnmount(() => {
  clearTimeout(reconnectTimer);
  clearInterval(statsTimer);
  clearInterval(recordsTimer);
  clearInterval(stateTimer);
  stopDemoReplay();
  if (socket) {
    socket.onopen = null; socket.onclose = null; socket.onerror = null; socket.onmessage = null;
    socket.close();
  }
});
</script>

<template>
  <div class="app-wrapper">
    <Transition name="health-splash">
      <div v-if="loadingSplash" class="health-splash-screen">
        <div class="splash-rings"><span></span><span></span><span></span></div>
        <img class="splash-monogram" src="/Logo.png" alt="SIGAIRE" />
        <h1>SIGAIRE</h1>
        <p>Sistema Inteligente de Gestión Autónoma de la Calidad del Aire</p>
        <div class="splash-progress"><i></i></div>
      </div>
    </Transition>

    <EnvironmentalHealthView
      v-if="!loadingSplash && !isAdminView"
      :state="displayState"
      :records="displayRecords"
      :ws-connected="wsConnected"
      :last-update="displayLastUpdate"
      :demo-mode="demoModeActive"
      @admin="isAdminView = true"
    />

    <div v-if="!loadingSplash && isAdminView" class="admin-wrapper">
      <div class="admin-mode-banner">
        <span><b>Panel técnico</b>SIGAIRE</span>
        <button type="button" @click="isAdminView = false">← Vista pública</button>
      </div>

      <div class="app-shell">
        <Sidebar :active="active" @change="active = $event" />

        <main class="main-content">
          <header class="topbar">
            <div>
              <span class="eyebrow">Sistema Inteligente de Gestión Autónoma de la Calidad del Aire</span>
              <h1>SIGAIRE</h1>
            </div>
            <div class="topbar-meta">
              <span class="connection-dot" :class="{ online: wsConnected }"></span>
              {{ wsConnected ? "Tiempo real" : "Reconectando" }}
            </div>
          </header>

          <div v-if="errorMessage" class="alert" role="alert">
            {{ errorMessage }}
            <button type="button" aria-label="Cerrar alerta" @click="errorMessage = ''">×</button>
          </div>

          <template v-if="active === 'dashboard'">
            <StatusCards :state="current" :ws-connected="wsConnected" />
            <AirQualityPanel :sensors="current.sensores || {}" />
            <AutonomousNavigationPanel :state="current" />
            <div class="dashboard-chart-grid">
              <AirQualityChart :records="records" />
              <TelemetryChart :records="records" />
            </div>
            <SensorPanel :sensors="current.sensores || {}" />
          </template>

          <template v-else-if="active === 'pm25'">
            <ParticleDashboard metric="pm25" :sensors="current.sensores || {}" :records="records" :stats="stats" />
          </template>

          <template v-else-if="active === 'pm10'">
            <ParticleDashboard metric="pm10" :sensors="current.sensores || {}" :records="records" :stats="stats" />
          </template>

          <template v-else-if="active === 'aire'">
            <AirQualityPanel :sensors="current.sensores || {}" />
            <AirQualityChart :records="records" />
            <SensorPanel :sensors="current.sensores || {}" />
          </template>

          <template v-else-if="active === 'historial'">
            <RecordsTable :records="records" :busy="busy" @refresh="loadRecords" @delete-record="removeRecord" @delete-all="removeAll" />
          </template>

          <template v-else>
            <SystemPanel :stats="stats" />
          </template>

          <footer>
            <span>Última actualización: {{ lastUpdate }}</span>
            <span>Raspberry Pi 5 · Base de datos local</span>
          </footer>
        </main>
      </div>
    </div>
  </div>
</template>

<style scoped>
.health-splash-screen {
  position: fixed; inset: 0; z-index: 9999; display: grid; place-content: center; justify-items: center;
  overflow: hidden; color: white; background: radial-gradient(circle at 50% 40%, #9b0047 0%, #85003d 48%, #65002e 100%);
}
.splash-monogram { position: relative; z-index: 2; width: 78px; height: 78px; display: grid; place-items: center; border-radius: 25px; background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.22); font-size: 27px; font-weight: 950; letter-spacing: -.05em; backdrop-filter: blur(8px); box-shadow: 0 20px 60px rgba(0,0,0,.18); animation: splash-float 1.5s ease-in-out infinite alternate; }
.health-splash-screen h1 { position: relative; z-index: 2; margin: 20px 0 5px; font-size: clamp(28px, 5vw, 46px); letter-spacing: .13em; text-align: center; }
.health-splash-screen p { position: relative; z-index: 2; margin: 0; color: rgba(255,255,255,.65); letter-spacing: .06em; font-size: 12px; }
.splash-progress { position: relative; z-index: 2; width: 190px; height: 4px; overflow: hidden; margin-top: 25px; border-radius: 99px; background: rgba(255,255,255,.12); }
.splash-progress i { display: block; height: 100%; width: 45%; border-radius: inherit; background: #ffd5e7; animation: splash-load 1.2s ease-in-out infinite; }
.splash-rings { position: absolute; width: 280px; height: 280px; }
.splash-rings span { position: absolute; inset: 0; border: 1px solid rgba(255,255,255,.12); border-radius: 50%; animation: splash-ring 2.4s ease-out infinite; }
.splash-rings span:nth-child(2) { animation-delay: .7s; }
.splash-rings span:nth-child(3) { animation-delay: 1.4s; }
.health-splash-leave-active { transition: opacity .45s ease, filter .45s ease; }
.health-splash-leave-to { opacity: 0; filter: blur(8px); }
.admin-mode-banner { display: flex; justify-content: space-between; align-items: center; gap: 14px; padding: 9px 18px; background: linear-gradient(90deg, #9b0047, #7f0039); color: white; font-size: 12px; }
.admin-mode-banner button { border: 1px solid rgba(255,255,255,.22); background: rgba(255,255,255,.08); color: white; border-radius: 999px; padding: 7px 11px; font-weight: 800; cursor: pointer; }
@keyframes splash-float { to { transform: translateY(-7px) rotate(1deg); } }
@keyframes splash-load { 0% { transform: translateX(-110%); } 100% { transform: translateX(280%); } }
@keyframes splash-ring { 0% { transform: scale(.35); opacity: 0; } 35% { opacity: .5; } 100% { transform: scale(1.45); opacity: 0; } }
</style>
