<script setup>
import { computed, ref, watch, onMounted, onUnmounted } from "vue";
import AdminLogin from "./AdminLogin.vue";

const props = defineProps({
  state: {
    type: Object,
    default: () => ({}),
  },
  records: {
    type: Array,
    default: () => [],
  },
  wsConnected: {
    type: Boolean,
    default: false,
  },
  lastUpdate: {
    type: String,
    default: "",
  },
  demoMode: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["admin"]);

const menuOpen = ref(false);
const settingsOpen = ref(false);
const loginOpen = ref(false);
const showHistory = ref(false);
const showAbout = ref(false);
const selectedHistory = ref(null);

// Ventana de información del sensor.
// - Con mouse: la tarjeta se inclina hacia el cursor y, tras un instante, la ventana crece
//   desde la tarjeta. Se mantiene abierta mientras el cursor esté sobre la tarjeta o la ventana.
//   Desaparece al quitar el cursor de ambas, encogiéndose hacia la tarjeta.
// - En táctil o con teclado: se abre con un toque / Enter y se cierra con ×, fuera o Esc.
const selectedSensor = ref(null);
const sensorModalMode = ref("hover"); // "hover" | "pinned"
const sensorOrigin = ref({ x: 0, y: 0 }); // desde dónde crece la ventana (centro de la tarjeta)
let sensorCloseTimer = null;
let sensorOpenTimer = null;

const reduceMotion =
  typeof window !== "undefined" &&
  !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

function setSensorOrigin(el) {
  const rect = el?.getBoundingClientRect?.();
  if (!rect) return;
  // La ventana está centrada en la pantalla: se calcula el desplazamiento al centro de la tarjeta.
  sensorOrigin.value = {
    x: Math.round(rect.left + rect.width / 2 - window.innerWidth / 2),
    y: Math.round(rect.top + rect.height / 2 - window.innerHeight / 2),
  };
}

function cancelSensorClose() {
  if (sensorCloseTimer) {
    clearTimeout(sensorCloseTimer);
    sensorCloseTimer = null;
  }
}

function cancelSensorOpen() {
  if (sensorOpenTimer) {
    clearTimeout(sensorOpenTimer);
    sensorOpenTimer = null;
  }
}

function scheduleSensorClose() {
  cancelSensorClose();
  sensorCloseTimer = setTimeout(() => {
    if (sensorModalMode.value === "hover") selectedSensor.value = null;
    sensorCloseTimer = null;
  }, 250);
}

// Inclinación 3D de la tarjeta hacia el cursor
function tiltCard(event) {
  if (event.pointerType !== "mouse" || reduceMotion) return;
  const el = event.currentTarget;
  const rect = el.getBoundingClientRect();
  const px = (event.clientX - rect.left) / rect.width - 0.5;
  const py = (event.clientY - rect.top) / rect.height - 0.5;
  el.style.setProperty("--rx", `${(-py * 8).toFixed(2)}deg`);
  el.style.setProperty("--ry", `${(px * 10).toFixed(2)}deg`);
}

function resetTilt(el) {
  el?.style?.setProperty("--rx", "0deg");
  el?.style?.setProperty("--ry", "0deg");
}

function hoverOpenSensor(card, event) {
  if (event?.pointerType !== "mouse") return;
  cancelSensorClose();
  cancelSensorOpen();
  setSensorOrigin(event.currentTarget);

  // Si ya hay una ventana abierta, cambia al instante; si no, espera un momento
  // para que se aprecie la inclinación de la tarjeta y no se abra al cruzar el mouse.
  if (selectedSensor.value) {
    selectedSensor.value = card;
    sensorModalMode.value = "hover";
    return;
  }
  sensorOpenTimer = setTimeout(() => {
    selectedSensor.value = card;
    sensorModalMode.value = "hover";
    sensorOpenTimer = null;
  }, reduceMotion ? 0 : 140);
}

function hoverCloseSensor(card, event) {
  if (event?.pointerType !== "mouse") return;
  cancelSensorOpen();
  if (sensorModalMode.value === "hover" && selectedSensor.value?.id === card.id) {
    scheduleSensorClose();
  }
}

function onCardLeave(card, event) {
  resetTilt(event.currentTarget);
  hoverCloseSensor(card, event);
}

function sensorWindowEnter(event) {
  if (event?.pointerType === "mouse") cancelSensorClose();
}

function sensorWindowLeave(event) {
  if (event?.pointerType === "mouse" && sensorModalMode.value === "hover") {
    scheduleSensorClose();
  }
}

function pinSensor(card, event) {
  // El clic de un mouse se ignora porque ya lo maneja el hover
  if (event?.pointerType === "mouse") return;
  cancelSensorClose();
  cancelSensorOpen();
  setSensorOrigin(event.currentTarget);
  selectedSensor.value = card;
  sensorModalMode.value = "pinned";
}

function pinSensorByKey(card, event) {
  cancelSensorClose();
  cancelSensorOpen();
  setSensorOrigin(event?.currentTarget);
  selectedSensor.value = card;
  sensorModalMode.value = "pinned";
}

function closeSensorDetail() {
  cancelSensorClose();
  cancelSensorOpen();
  selectedSensor.value = null;
}

// Copia local de respaldo: permite consultar las últimas mediciones aunque
// MeteoBot o la conexión con el servidor no estén disponibles.
const LOCAL_HISTORY_KEY = "sigaire_meteobot_history_v1";
const localRecords = ref([]);

function readLocalHistory() {
  try {
    const saved = JSON.parse(localStorage.getItem(LOCAL_HISTORY_KEY) || "[]");
    localRecords.value = Array.isArray(saved) ? saved : [];
  } catch {
    localRecords.value = [];
  }
}

function persistLocalHistory(records) {
  try {
    const merged = [...localRecords.value, ...(Array.isArray(records) ? records : [])];
    const unique = new Map();
    merged.forEach((record) => {
      const stamp = record?.timestamp || record?.fecha || record?.created_at;
      const id = record?.id ?? record?._id;
      const key = id !== undefined ? `id:${id}` : `${stamp || "sin-fecha"}:${JSON.stringify(record)}`;
      unique.set(key, record);
    });
    const ordered = [...unique.values()]
      .sort((a, b) => new Date(a.timestamp || a.fecha || 0) - new Date(b.timestamp || b.fecha || 0))
      .slice(-20000);
    localRecords.value = ordered;
    localStorage.setItem(LOCAL_HISTORY_KEY, JSON.stringify(ordered));
  } catch (error) {
    console.warn("No fue posible guardar el respaldo local del historial:", error);
  }
}

// Pronóstico meteorológico de Open-Meteo para la ubicación de referencia
// del sistema: Tecnológico de Estudios Superiores de San Felipe del Progreso.
const weatherData = ref(null);
const weatherLoading = ref(false);
const weatherError = ref(false);
const weatherLocation = ref(null);
let weatherRefreshTimer = null;

async function loadWeatherForecast() {
  weatherLoading.value = true;
  weatherError.value = false;

  try {
    if (!weatherLocation.value) {
      const geoUrl = new URL("https://geocoding-api.open-meteo.com/v1/search");
      geoUrl.search = new URLSearchParams({
        name: "San Felipe del Progreso",
        count: "1",
        language: "es",
        format: "json",
        countryCode: "MX",
      }).toString();
      const geoResponse = await fetch(geoUrl.toString());
      if (!geoResponse.ok) throw new Error("No fue posible localizar el municipio.");
      const geoJson = await geoResponse.json();
      const place = geoJson?.results?.[0];
      if (!place || !Number.isFinite(Number(place.latitude)) || !Number.isFinite(Number(place.longitude))) {
        throw new Error("Open-Meteo no devolvió coordenadas para la ubicación.");
      }
      weatherLocation.value = {
        latitude: Number(place.latitude),
        longitude: Number(place.longitude),
        name: place.name || "San Felipe del Progreso",
      };
    }

    const forecastUrl = new URL("https://api.open-meteo.com/v1/forecast");
    forecastUrl.search = new URLSearchParams({
      latitude: String(weatherLocation.value.latitude),
      longitude: String(weatherLocation.value.longitude),
      current: "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,showers,weather_code,is_day,cloud_cover,wind_speed_10m",
      hourly: "precipitation_probability,precipitation,uv_index,temperature_2m,weather_code",
      daily: "uv_index_max,precipitation_probability_max,weather_code,temperature_2m_max,temperature_2m_min",
      forecast_days: "1",
      timezone: "auto",
    }).toString();

    const response = await fetch(forecastUrl.toString());
    if (!response.ok) throw new Error("No fue posible consultar el pronóstico.");
    const data = await response.json();
    if (!data?.current) throw new Error("El pronóstico no contiene condiciones actuales.");

    const hourlyTimes = data.hourly?.time || [];
    const currentTime = data.current.time;
    let currentIndex = hourlyTimes.indexOf(currentTime);
    if (currentIndex < 0 && hourlyTimes.length) {
      const now = new Date(currentTime || Date.now()).getTime();
      currentIndex = hourlyTimes.reduce((best, item, index) => {
        const distance = Math.abs(new Date(item).getTime() - now);
        return distance < best.distance ? { index, distance } : best;
      }, { index: 0, distance: Infinity }).index;
    }
    const probabilities = (data.hourly?.precipitation_probability || [])
      .slice(Math.max(0, currentIndex), Math.max(0, currentIndex) + 4)
      .filter((value) => value !== null && Number.isFinite(Number(value)))
      .map(Number);
    const rainAmounts = (data.hourly?.precipitation || [])
      .slice(Math.max(0, currentIndex), Math.max(0, currentIndex) + 4)
      .filter((value) => value !== null && Number.isFinite(Number(value)))
      .map(Number);
    const uvValues = (data.hourly?.uv_index || [])
      .slice(Math.max(0, currentIndex), Math.max(0, currentIndex) + 4)
      .filter((value) => value !== null && Number.isFinite(Number(value)))
      .map(Number);

    weatherData.value = {
      current: data.current,
      daily: data.daily || {},
      precipitationProbabilityNextHours: probabilities.length ? Math.max(...probabilities) : null,
      precipitationNextHours: rainAmounts.length ? Math.max(...rainAmounts) : null,
      uvNextHours: uvValues.length ? Math.max(...uvValues) : Number(data.daily?.uv_index_max?.[0] ?? 0),
      locationName: weatherLocation.value.name,
      updatedAt: new Date().toISOString(),
    };
  } catch (error) {
    console.warn("No fue posible actualizar el pronóstico de Open-Meteo:", error);
    weatherError.value = true;
    // Conserva el último pronóstico válido si la API falla temporalmente.
  } finally {
    weatherLoading.value = false;
  }
}

const weatherStatusText = computed(() => {
  if (weatherLoading.value && !weatherData.value) return "Consultando pronóstico meteorológico de Open-Meteo…";
  if (weatherData.value) return `Pronóstico de Open-Meteo · ${weatherData.value.locationName} · se actualiza cada 15 minutos.`;
  if (weatherError.value) return "Pronóstico meteorológico temporalmente no disponible; se utilizan las lecturas de MeteoBot.";
  return "Pronóstico meteorológico pendiente de consulta.";
});

onMounted(() => {
  readLocalHistory();
  if (props.records?.length) persistLocalHistory(props.records);
  loadWeatherForecast();
  weatherRefreshTimer = setInterval(loadWeatherForecast, 15 * 60 * 1000);
});

onUnmounted(() => {
  if (weatherRefreshTimer) clearInterval(weatherRefreshTimer);
  cancelSensorClose();
  cancelSensorOpen();
});

watch(
  () => props.records,
  (records) => {
    if (Array.isArray(records) && records.length) persistLocalHistory(records);
  },
  { deep: true }
);

function parseRecordDate(value) {
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
  if (value === null || value === undefined || value === "") return null;

  const raw = String(value).trim();
  // Prioriza el formato mexicano dd/mm/aaaa para evitar interpretaciones mm/dd.
  const mx = raw.match(/^(\d{1,2})[\/-](\d{1,2})[\/-](\d{4})(?:[ T,]+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?)?$/i);
  if (mx) {
    let hour = Number(mx[4] || 0);
    const meridiem = (mx[7] || "").toLowerCase().replace(/\./g, "");
    if (meridiem === "pm" && hour < 12) hour += 12;
    if (meridiem === "am" && hour === 12) hour = 0;
    const date = new Date(Number(mx[3]), Number(mx[2]) - 1, Number(mx[1]), hour, Number(mx[5] || 0), Number(mx[6] || 0));
    return Number.isNaN(date.getTime()) ? null : date;
  }

  const parsed = new Date(raw);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function recordDate(record) {
  return parseRecordDate(
    record?.timestamp ?? record?.fecha ?? record?.Fecha ?? record?.created_at ?? record?.createdAt
  );
}

const allRecords = computed(() => {
  const merged = new Map();
  [...localRecords.value, ...(props.records || [])].forEach((record) => {
    const stamp = record?.timestamp || record?.fecha || record?.Fecha || record?.created_at;
    const id = record?.id ?? record?._id;
    const key = id !== undefined ? `id:${id}` : `${stamp || "sin-fecha"}:${JSON.stringify(record)}`;
    merged.set(key, record);
  });
  return [...merged.values()];
});

const sensors = computed(() => props.state?.sensores || {});

function normalizeSensorKey(value) {
  return String(value ?? "")
    .replace(/₂/g, "2")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
}

function unwrapSensorValue(value) {
  if (value === undefined || value === null || value === "") return null;
  if (typeof value === "object") {
    return value.valor ?? value.value ?? value.ppm ?? value.ugm3 ??
      value.voltage ?? value.voltaje ?? value.concentracion ?? value.raw ?? null;
  }
  return value;
}

function getSensorValue(sensor, ...keys) {
  if (!sensor || typeof sensor !== "object") return null;

  for (const key of keys) {
    const value = unwrapSensorValue(sensor[key]);
    if (value !== null && value !== undefined && value !== "") return value;
  }

  // Acepta encabezados con acentos, subíndices, espacios o unidades, por
  // ejemplo "CO₂ (ppm)", "PM2.5" y "Temperatura (°C)".
  const entries = Object.entries(sensor);
  for (const key of keys) {
    const wanted = normalizeSensorKey(key);
    const match = entries.find(([actual]) => normalizeSensorKey(actual) === wanted);
    if (match) {
      const value = unwrapSensorValue(match[1]);
      if (value !== null && value !== undefined && value !== "") return value;
    }
  }

  return null;
}

function num(value, decimals = 1) {
  if (value === null || value === undefined || value === "") return null;

  const parsed = Number(value);

  return Number.isFinite(parsed) ? parsed.toFixed(decimals) : null;
}

function formatValue(value, decimals = 1) {
  const result = num(value, decimals);
  return result === null ? "—" : result;
}

function isCalibrated(value) {
  return value === true || value === 1 || value === "1" || value === "true";
}

const pm25 = computed(() =>
  getSensorValue(sensors.value, "pm25_filtered", "pm25", "PM2_5", "pm2_5", "pm2.5", "PM2.5 (µg/m³)") ??
  latestHistoricalSensorValue("pm25_filtered", "pm25", "PM2_5", "pm2_5", "pm2.5", "PM2.5 (µg/m³)")
);

const pm10 = computed(() =>
  getSensorValue(sensors.value, "pm10_filtered", "pm10", "PM10", "PM10 (µg/m³)") ??
  latestHistoricalSensorValue("pm10_filtered", "pm10", "PM10", "PM10 (µg/m³)")
);

const temperature = computed(() =>
  getSensorValue(sensors.value, "temperatura", "temperature", "temp", "Temperatura (°C)") ??
  latestHistoricalSensorValue("temperatura", "temperature", "temp", "Temperatura (°C)")
);

const humidity = computed(() =>
  getSensorValue(sensors.value, "humedad", "humidity", "hum", "HR (%)") ??
  latestHistoricalSensorValue("humedad", "humidity", "hum", "HR (%)")
);

const co2Calibrated = computed(() =>
  isCalibrated(
    getSensorValue(sensors.value, "mg811_calibrado", "co2_calibrado")
  )
);

const co2Live = computed(() => {
  const value = getSensorValue(sensors.value, "co2", "CO2", "co2_ppm", "mg811_co2_ppm", "CO₂ (ppm)");

  if (!co2Calibrated.value || value === null || Number(value) <= 0) {
    return null;
  }

  return value;
});

// Busca la última lectura válida de cada sensor en el historial.
// El panel público no debe depender exclusivamente de props.state.sensores,
// porque ese objeto puede venir vacío cuando MeteoBot deja de transmitir.
function latestHistoricalSensorValue(...keys) {
  const ordered = [...allRecords.value].sort((a, b) =>
    (recordDate(b)?.getTime() || 0) - (recordDate(a)?.getTime() || 0)
  );

  for (const record of ordered) {
    const data = getRecordSensors(record);
    const value = getSensorValue(data, ...keys);
    if (value !== null && Number.isFinite(Number(value))) return value;
  }
  return null;
}

function latestHistoricalSensorState(key) {
  const ordered = [...allRecords.value].sort((a, b) =>
    (recordDate(b)?.getTime() || 0) - (recordDate(a)?.getTime() || 0)
  );

  for (const record of ordered) {
    const data = getRecordSensors(record);
    const value = getSensorValue(data, key);
    if (value !== null) return value;
  }
  return null;
}

const mg811AoutValue = computed(() =>
  getSensorValue(
    sensors.value,
    "mg811_aout_v",
    "mg811_aout",
    "mg811_voltage",
    "mg811_vo",
    "MG811 AOUT (V)"
  ) ?? latestHistoricalSensorValue("mg811_aout_v", "mg811_aout", "mg811_voltage", "mg811_vo", "MG811 AOUT (V)")
);

const sharpValue = computed(() =>
  getSensorValue(
    sensors.value,
    "sharp_vo_v",
    "sharp",
    "gp2y1014",
    "sharp_gp2y1014",
    "polvo_sharp",
    "Sharp Vo (V)"
  ) ?? latestHistoricalSensorValue("sharp_vo_v", "Sharp Vo (V)")
);

const bfsValue = computed(() =>
  getSensorValue(
    sensors.value,
    "bfs302_aout_v",
    "bfs302",
    "bfs_302",
    "humo",
    "gas_bfs302",
    "BFS AOUT (V)"
  ) ?? latestHistoricalSensorValue("bfs302_aout_v", "BFS AOUT (V)")
);

const sharpState = computed(() =>
  getSensorValue(sensors.value, "sharp_estado") ??
  latestHistoricalSensorState("sharp_estado")
);

const bfsState = computed(() =>
  getSensorValue(sensors.value, "bfs302_estado") ??
  latestHistoricalSensorState("bfs302_estado")
);

const latestRecord = computed(() => {
  if (!allRecords.value.length) return null;

  return [...allRecords.value].sort((a, b) =>
    (recordDate(b)?.getTime() || 0) - (recordDate(a)?.getTime() || 0)
  )[0];
});

const historicalCo2 = computed(() => {
  const ordered = [...allRecords.value].sort((a, b) =>
    (recordDate(b)?.getTime() || 0) - (recordDate(a)?.getTime() || 0)
  );

  // Busca hacia atrás la última lectura real de CO₂; no se limita al último
  // registro general, que puede existir aunque ese sensor no haya reportado.
  for (const record of ordered) {
    const data = getRecordSensors(record);
    const value = getSensorValue(data, "co2", "CO2", "co2_ppm", "mg811_co2_ppm", "CO₂ (ppm)");
    const calibrated = isCalibrated(getSensorValue(data, "mg811_calibrado", "co2_calibrado"));
    if (calibrated && value !== null && Number.isFinite(Number(value)) && Number(value) > 0) {
      return value;
    }
  }
  return null;
});

const co2Value = computed(() => {
  return co2Live.value ?? historicalCo2.value;
});

const co2IsHistorical = computed(() => {
  return co2Live.value === null && historicalCo2.value !== null;
});


function cleanCardStatus(status) {
  if (status === null || status === undefined) return "";
  return String(status)
    .replace(/\s*[·•-]\s*(?:\d{1,2}\s+[a-záéíóúñ]+\s+\d{4}|\d{1,2}[\/-]\d{1,2}[\/-]\d{2,4})(?:[, ]+.*)?$/i, "")
    .replace(/\s*[·•-]\s*\d{1,2}:\d{2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?$/i, "")
    .trim();
}

function sensorLevel(type, value) {
  if (value === null || value === undefined || value === "") {
    return {
      text: "Sin datos",
      tone: "neutral",
      percent: 0,
    };
  }

  const n = Number(value);

  if (!Number.isFinite(n)) {
    return {
      text: "Sin datos",
      tone: "neutral",
      percent: 0,
    };
  }

  // Bandas orientativas de clasificación para la lectura disponible.
  // No equivalen al índice oficial si no se cuenta con el promedio móvil
  // ponderado y el procedimiento de cálculo establecido para ese índice.
  if (type === "pm25") {
    if (n <= 15) return { text: "Buena · riesgo bajo", tone: "good", percent: 15, emoji: "😊" };
    if (n <= 25) return { text: "Aceptable · riesgo moderado", tone: "warning", percent: 35, emoji: "🙂" };
    if (n <= 79) return { text: "Mala · riesgo alto", tone: "danger", percent: 60, emoji: "😷" };
    if (n <= 130) return { text: "Muy mala · riesgo muy alto", tone: "danger", percent: 82, emoji: "🤧" };
    return { text: "Extremadamente mala", tone: "danger", percent: 100, emoji: "🚨" };
  }

  if (type === "pm10") {
    if (n <= 45) return { text: "Buena · riesgo bajo", tone: "good", percent: 15, emoji: "😊" };
    if (n <= 50) return { text: "Aceptable · riesgo moderado", tone: "warning", percent: 35, emoji: "🙂" };
    if (n <= 132) return { text: "Mala · riesgo alto", tone: "danger", percent: 60, emoji: "😷" };
    if (n <= 213) return { text: "Muy mala · riesgo muy alto", tone: "danger", percent: 82, emoji: "🤧" };
    return { text: "Extremadamente mala", tone: "danger", percent: 100, emoji: "🚨" };
  }

  if (type === "co2") {
    if (n <= 800) return { text: "Nivel orientativo bajo", tone: "good", percent: 25, emoji: "😊" };
    if (n <= 1200) return { text: "Conviene ventilar", tone: "warning", percent: 60, emoji: "🪟" };
    return { text: "Concentración elevada", tone: "danger", percent: 95, emoji: "⚠️" };
  }

  if (type === "temperature") {
    if (n >= 18 && n <= 27) {
      return { text: "Favorable", tone: "good", percent: 35, emoji: "🌤️" };
    }

    if (n >= 15 && n <= 32) {
      return { text: "Moderado", tone: "warning", percent: 60, emoji: "🌥️" };
    }

    return { text: "Fuera de rango", tone: "danger", percent: 90, emoji: "🌡️" };
  }

  return { text: "Dato recibido", tone: "neutral", percent: 35 };
}


function sensorEnvironmentExamples(id) {
  const examples = {
    pm25: "Humo de incendios y quemas, combustión de vehículos, estufas, quema de basura, humo de tabaco y algunas actividades industriales.",
    pm10: "Polvo de caminos y obras, tierra removida, actividades agrícolas, construcción, trituración de materiales y emisiones de vehículos.",
    mg811: "Las variaciones de la señal pueden relacionarse con cambios en el aire alrededor del sensor; la salida en voltios no identifica por sí sola una concentración de CO₂.",
    co2: "Personas reunidas en espacios cerrados, ventilación insuficiente y acumulación de aire interior.",
    temperature: "La exposición al sol, la sombra, la ventilación, la hora del día y las condiciones meteorológicas modifican la temperatura y la humedad.",
    sharp: "Polvo y partículas presentes en el aire que atraviesan la zona de detección óptica del sensor.",
    bfs: "Presencia de humo o ciertos gases en el entorno, de acuerdo con la sensibilidad y configuración del módulo."
  };
  return examples[id] || "Condiciones del entorno que pueden modificar la lectura del sensor.";
}

function sensorRecommendation(card) {
  const n = Number(card.rawValue);
  const valid = card.rawValue !== null && card.rawValue !== undefined &&
    card.rawValue !== "" && Number.isFinite(n);
  const weather = weatherData.value;
  const current = weather?.current || {};
  const rainProbability = Number(weather?.precipitationProbabilityNextHours);
  const uv = Number(weather?.uvNextHours);
  const weatherCode = Number(current.weather_code);
  const rainy = (Number.isFinite(rainProbability) && rainProbability >= 55) ||
    [51, 53, 55, 61, 63, 65, 80, 81, 82, 95, 96, 99].includes(weatherCode);
  const humidityReading = Number(humidity.value);
  const hasHumidity = humidity.value !== null && humidity.value !== undefined &&
    humidity.value !== "" && Number.isFinite(humidityReading);

  if (!valid) {
    return "Todavía no hay una lectura disponible. Cuando el sensor envíe un valor válido, se mostrará aquí una recomendación relacionada con esa medición.";
  }

  if (card.id === "pm25") {
    if (n > 79) return "🚨 PM2.5 está elevado. Evita el humo, las quemas y las emisiones; reduce el ejercicio al aire libre y, si es posible, permanece en un espacio interior con aire limpio.";
    if (n > 25) return "⚠️ PM2.5 requiere atención. Evita actividades intensas al aire libre, aléjate de fuentes de humo y cierra puertas y ventanas si entra contaminación desde el exterior.";
    if (n > 15) return "🌫️ PM2.5 está en un tramo moderado. Si notas humo o polvo, limita el tiempo que permaneces en esa zona y procura hacer ejercicio cuando el aire esté más limpio.";
    return "🌿 PM2.5 está en el tramo bajo de referencia. Puedes realizar tus actividades habituales; evita quemar basura, hojas o cualquier material para cuidar la calidad del aire.";
  }

  if (card.id === "pm10") {
    if (n > 132) return "🚧 PM10 está elevado. Evita zonas con polvo, obras o caminos sin pavimentar; procura permanecer en interiores si hay polvo suspendido y evita barrer en seco.";
    if (n > 50) return "⚠️ PM10 requiere atención. Aléjate de construcciones, tierra suelta y tránsito que levante polvo. Para limpiar, utiliza métodos húmedos en lugar de sacudir o barrer en seco.";
    if (n > 45) return "🌬️ PM10 está en un tramo moderado. Si vas a transitar por zonas polvorientas, reduce el tiempo de exposición y evita levantar polvo.";
    return "🌱 PM10 está en el tramo bajo de referencia. Mantén limpias las áreas sin levantar polvo y evita quemas o actividades que dispersen partículas.";
  }

  if (card.id === "temperature") {
    const temp = n;
    const advice = [];
    if (temp <= 5) {
      advice.push("🥶 Hace mucho frío: usa chamarra gruesa, suéter y calzado cerrado; procura limitar el tiempo a la intemperie.");
    } else if (temp <= 12) {
      advice.push("🧥 El ambiente está frío: ponte chamarra y una prenda abrigadora, como un suéter, si vas a salir.");
    } else if (temp < 18) {
      advice.push("🌥️ El ambiente está fresco: lleva un suéter o chamarra ligera, especialmente por la mañana o al anochecer.");
    } else if (temp <= 27) {
      advice.push("🌤️ La temperatura es templada: utiliza ropa cómoda y ligera; no se requiere abrigo adicional por la temperatura registrada.");
    } else if (temp <= 32) {
      advice.push("☀️ El ambiente está caluroso: usa ropa ligera, toma agua y busca sombra si permaneces al aire libre.");
    } else {
      advice.push("🥵 La temperatura es muy alta: evita exponerte al sol durante las horas de mayor calor, permanece en lugares frescos, hidrátate y limita el esfuerzo físico.");
    }

    if (hasHumidity && humidityReading >= 75) {
      advice.push("💧 La humedad también es alta; usa ropa fresca y procura estar en un lugar ventilado.");
    } else if (hasHumidity && humidityReading <= 30) {
      advice.push("🚰 La humedad es baja; mantente hidratado y evita permanecer mucho tiempo en ambientes secos.");
    } else if (hasHumidity && humidityReading >= 60) {
      advice.push("💦 La humedad es moderadamente alta; toma descansos si realizas actividad física.");
    }
    if (Number.isFinite(uv) && uv >= 6) {
      advice.push("🧴 El pronóstico indica radiación UV elevada: usa gorra, protector solar y busca sombra.");
    }
    if (rainy) advice.push("🌧️ Hay posibilidad de lluvia: lleva paraguas o impermeable.");
    return advice.join(" ");
  }

  if (card.id === "co2") {
    if (n >= 1500) return "🚨 La concentración calibrada de CO₂ es elevada. Si estás en interiores, ventila el espacio abriendo puertas o ventanas cuando el aire exterior sea adecuado; reduce la cantidad de personas en el lugar si es posible y vuelve a medir.";
    if (n >= 1000) return "⚠️ La concentración calibrada de CO₂ está aumentando. Renueva el aire abriendo una ventana o puerta y revisa nuevamente la lectura después de ventilar.";
    if (n >= 800) return "🪟 La lectura se encuentra en un nivel intermedio de referencia. Mantén una ventilación constante, especialmente si hay varias personas en el mismo espacio.";
    return "✅ La lectura calibrada de CO₂ es baja dentro de los tramos configurados. Mantén la ventilación habitual y continúa observando si aumenta cuando se ocupa el espacio.";
  }
  if (card.id === "mg811") {
    return "🔬 El valor actual es " + n.toFixed(3) + " V. Corresponde a la salida analógica del MG811 y no permite determinar por sí solo si el CO₂ está alto o bajo. Mantén el sensor en un lugar ventilado, evita obstruirlo y compara sus cambios con registros tomados bajo condiciones similares. Para recomendar ventilación según ppm se necesita calibrar esta señal.";
  }
  if (card.id === "sharp") {
    return "🔎 El sensor está entregando " + n.toFixed(2) + " V. Este voltaje no equivale directamente a una concentración de partículas. Mantén despejada y limpia la entrada óptica; registra las variaciones y evita clasificar el aire como limpio o contaminado hasta contar con una calibración.";
  }
  if (card.id === "bfs") {
    return "📟 La señal actual es de " + n.toFixed(2) + " V. Como todavía no está convertida mediante calibración a una concentración de gas o humo, no es posible indicar un nivel de exposición. Mantén el módulo alejado de humedad y polvo excesivos y compara la lectura con su valor base para detectar cambios.";
  }
  return "📊 Continúa observando este valor y compáralo con los registros anteriores para identificar cambios en el entorno.";
}

const allSensors = computed(() => {
  const pm25Status = sensorLevel("pm25", pm25.value);
  const pm10Status = sensorLevel("pm10", pm10.value);
  const tempStatus = sensorLevel("temperature", temperature.value);

  return [
    {
      id: "pm25",
      rawValue: pm25.value,
      title: "Partículas PM2.5",
      source: "SDS011",
      value: formatValue(pm25.value, 1),
      unit: "µg/m³",
      description: "Partículas finas suspendidas en el aire",
      status: pm25Status.text,
      emoji: pm25Status.emoji || "🌫️",
      tone: pm25Status.tone,
      percent: pm25Status.percent,
      detail:
        "El sensor SDS011 permite obtener mediciones de partículas finas PM2.5 presentes en el ambiente.",
      iconType: "pm25"
    },
    {
      id: "pm10",
      rawValue: pm10.value,
      title: "Partículas PM10",
      source: "SDS011",
      value: formatValue(pm10.value, 1),
      unit: "µg/m³",
      description: "Partículas suspendidas de mayor tamaño",
      status: pm10Status.text,
      emoji: pm10Status.emoji || "🌫️",
      tone: pm10Status.tone,
      percent: pm10Status.percent,
      detail:
        "El valor PM10 representa la concentración de partículas suspendidas con un diámetro aerodinámico de hasta 10 micrómetros.",
      iconType: "pm10"
    },
    {
      id: "mg811",
      rawValue: mg811AoutValue.value,
      title: "MG811 AOUT",
      source: "mg811_aout_v",
      value: formatValue(mg811AoutValue.value, 3),
      unit: "V",
      description: "Señal analógica del sensor MG811",
      status: mg811AoutValue.value !== null ? "Lectura de voltaje recibida" : "Sin datos",
      emoji: mg811AoutValue.value !== null ? "🔬" : "📡",
      tone: "neutral",
      percent: mg811AoutValue.value !== null ? 35 : 0,
      detail: "El valor MG811 AOUT corresponde al voltaje de salida del sensor. No representa una concentración de CO₂ en ppm. Para convertirlo a ppm se necesita calibración y una curva de conversión validada.",
      iconType: "mg811"
    },
    ...(co2Value.value !== null ? [{
      id: "co2",
      rawValue: co2Value.value,
      title: "CO₂ calibrado",
      source: "MG811",
      value: formatValue(co2Value.value, 0),
      unit: "ppm",
      description: "Concentración estimada de dióxido de carbono",
      status: "Lectura calibrada disponible",
      emoji: "🫧",
      tone: "neutral",
      percent: 35,
      detail: "La concentración en ppm se muestra únicamente cuando el MG811 cuenta con una lectura marcada como calibrada.",
      iconType: "co2"
    }] : []),
    {
      id: "temperature",
      rawValue: temperature.value,
      title: "Temperatura y humedad",
      source: "SHT3x",
      value: formatValue(temperature.value, 1),
      unit: "°C",
      humidity: formatValue(humidity.value, 1),
      humidityUnit: "%",
      description: "Condiciones ambientales",
      status: tempStatus.text,
      emoji: tempStatus.emoji || "🌡️",
      tone: tempStatus.tone,
      percent: tempStatus.percent,
      detail:
        "El sensor SHT3x permite consultar la temperatura y humedad relativa del ambiente.",
      iconType: "temp"
    },
    {
      id: "sharp",
      rawValue: sharpValue.value,
      title: "Sharp GP2Y1010AU0F",
      source: "sharp_vo_v",
      value: formatValue(sharpValue.value, 2),
      unit: "V",
      description: "Sensor óptico de partículas",
      status: sharpState.value || (sharpValue.value !== null ? "Última lectura guardada" : "Sin datos"),
      tone: sharpValue.value !== null ? "good" : "neutral",
      percent: sharpValue.value !== null ? 35 : 0,
      detail:
        "La columna sharp_vo_v registra el voltaje de salida (Vo) del sensor óptico Sharp GP2Y1010AU0F. Es una señal eléctrica del sensor y no una concentración PM2.5 directa.",
      iconType: "sharp"
    },
    {
      id: "bfs",
      rawValue: bfsValue.value,
      title: "BFS-302",
      source: "bfs302_aout_v",
      value: formatValue(bfsValue.value, 2),
      unit: "V",
      description: "Sensor de gases y humos",
      status: bfsState.value || (bfsValue.value !== null ? "Última lectura guardada" : "Sin datos"),
      tone: bfsValue.value !== null ? "good" : "neutral",
      percent: bfsValue.value !== null ? 35 : 0,
      detail:
        "El BFS-302 proporciona una señal de salida que permite observar cambios en la detección de humo o gases, de acuerdo con su configuración.",
      iconType: "bfs"
    },
  ];
});

const historyByDay = computed(() => {
  const grouped = {};

  allRecords.value.forEach((record) => {
    const date = recordDate(record);
    if (!date) return;

    const key = [
      date.getFullYear(),
      String(date.getMonth() + 1).padStart(2, "0"),
      String(date.getDate()).padStart(2, "0"),
    ].join("-");

    if (!grouped[key]) {
      grouped[key] = {
        date: key,
        timestamp: date,
        records: [],
      };
    }

    grouped[key].records.push(record);
  });

  return Object.values(grouped)
    .sort((a, b) => b.timestamp - a.timestamp);
});


const todayDateLabel = computed(() => new Date().toLocaleDateString("es-MX", {
  day: "numeric", month: "long", year: "numeric"
}));

const todayHistorySummary = computed(() => {
  const now = new Date();
  const todayKey = [now.getFullYear(), String(now.getMonth() + 1).padStart(2, "0"), String(now.getDate()).padStart(2, "0")].join("-");
  const todayRecords = historyByDay.value.find((day) => day.date === todayKey);
  if (todayRecords) {
    return { ...getDayCondition(todayRecords), source: `${todayRecords.records.length} registro(s) de MeteoBot` };
  }

  const currentWeather = weatherData.value?.current || {};
  const code = Number(currentWeather.weather_code);
  const rainProbability = Number(weatherData.value?.precipitationProbabilityNextHours);
  if (!weatherData.value) {
    return { emoji: "📊", label: "Aún no hay registros de MeteoBot para hoy", source: "Sin datos del día" };
  }
  if ((Number.isFinite(rainProbability) && rainProbability >= 55) || [51, 53, 55, 61, 63, 65, 80, 81, 82, 95, 96, 99].includes(code)) {
    return { emoji: "🌧️", label: "Día con probabilidad de lluvia", source: "Estimación del pronóstico meteorológico" };
  }
  if ([0, 1].includes(code)) return { emoji: "☀️", label: "Día despejado", source: "Estimación del pronóstico meteorológico" };
  if ([2, 3, 45, 48].includes(code)) return { emoji: "🌥️", label: "Día parcialmente nublado", source: "Estimación del pronóstico meteorológico" };
  if (Number(currentWeather.temperature_2m) >= 30) return { emoji: "🥵", label: "Día caluroso", source: "Estimación del pronóstico meteorológico" };
  if (Number(currentWeather.temperature_2m) <= 12) return { emoji: "🧥", label: "Día frío", source: "Estimación del pronóstico meteorológico" };
  return { emoji: "🌤️", label: "Condiciones variables", source: "Pronóstico meteorológico; sin registros del robot hoy" };
});

function getRecordSensors(record) {
  return record?.sensores || record?.sensor || record?.data || record || {};
}

function getHistoryValues(day) {
  // Solo se muestran los mismos valores que aparecen en las tarjetas principales.
  const fields = [
    ["PM2.5", ["pm25_filtered", "pm25", "PM2.5", "PM2.5 (µg/m³)"], 1, "µg/m³"],
    ["PM10", ["pm10_filtered", "pm10", "PM10", "PM10 (µg/m³)"], 1, "µg/m³"],
    ["MG811 AOUT", ["mg811_aout_v", "MG811 AOUT (V)"], 3, "V"],
    ["CO₂ calibrado", ["co2", "CO2", "co2_ppm", "mg811_co2_ppm", "CO₂ (ppm)"], 0, "ppm"],
    ["Temperatura", ["temperatura", "temperature", "temp", "Temp (°C)", "Temperatura (°C)"], 1, "°C"],
    ["Humedad", ["humedad", "humidity", "hum", "HR (%)"], 1, "%"],
    ["Sharp Vo", ["sharp_vo_v", "Sharp Vo (V)"], 3, "V"],
    ["BFS AOUT", ["bfs302_aout_v", "BFS AOUT (V)"], 3, "V"],
  ];

  const rows = day.records.map(getRecordSensors);
  return fields.map(([label, keys, decimals, unit]) => {
    // El CO₂ solo cuenta cuando la lectura está marcada como calibrada.
    const source = label === "CO₂ calibrado"
      ? rows.filter((row) => isCalibrated(getSensorValue(row, "mg811_calibrado", "co2_calibrado")))
      : rows;
    const values = source
      .map((row) => getSensorValue(row, ...keys))
      .filter((value) => value !== null && value !== undefined && value !== "");

    if (!values.length) return null;

    const numericValues = values.map(Number).filter(Number.isFinite);
    if (decimals !== null && numericValues.length) {
      const average = numericValues.reduce((sum, value) => sum + value, 0) / numericValues.length;
      const minimum = Math.min(...numericValues);
      const maximum = Math.max(...numericValues);
      return {
        label,
        value: `Prom. ${formatValue(average, decimals)} · ${formatValue(minimum, decimals)}–${formatValue(maximum, decimals)}`,
        unit,
        count: numericValues.length,
      };
    }

    const latest = values[values.length - 1];
    return {
      label,
      value: typeof latest === "boolean" ? (latest ? "Sí" : "No") : String(latest),
      unit,
      count: values.length,
    };
  }).filter(Boolean);
}

function getDayCondition(day) {
  const values = day.records.map(getRecordSensors);
  const p25 = values
    .map((item) => getSensorValue(item, "pm25_filtered", "pm25", "PM2.5", "PM2.5 (µg/m³)"))
    .filter((value) => value !== null && value !== undefined && value !== "")
    .map(Number)
    .filter(Number.isFinite);
  const p10 = values
    .map((item) => getSensorValue(item, "pm10_filtered", "pm10", "PM10 (µg/m³)"))
    .filter((value) => value !== null && value !== undefined && value !== "")
    .map(Number)
    .filter(Number.isFinite);
  const status25 = p25.length ? sensorLevel("pm25", Math.max(...p25)) : null;
  const status10 = p10.length ? sensorLevel("pm10", Math.max(...p10)) : null;

  if ([status25, status10].some((status) => status?.tone === "danger")) {
    return { emoji: "😷", label: "Día con lecturas máximas elevadas" };
  }
  if ([status25, status10].some((status) => status?.tone === "warning")) {
    return { emoji: "🌥️", label: "Día con lecturas máximas de precaución" };
  }
  if (status25 || status10) return { emoji: "😊", label: "Día con lecturas máximas favorables" };
  return { emoji: "📊", label: "Sin datos suficientes" };
}

function formatHistoryDate(value) {
  return new Date(value).toLocaleDateString("es-MX", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}


function openHistoryDay(day) {
  selectedHistory.value =
    selectedHistory.value?.date === day.date ? null : day;
}

function openHistory() {
  showAbout.value = false;
  showHistory.value = true;
  menuOpen.value = false;
  settingsOpen.value = false;
  selectedHistory.value = null;
}

function closeHistory() {
  showHistory.value = false;
  selectedHistory.value = null;
}

function goHome() {
  showAbout.value = false;
  showHistory.value = false;
  menuOpen.value = false;
  settingsOpen.value = false;
}

function scrollToId(id) {
  showAbout.value = false;
  showHistory.value = false;
  menuOpen.value = false;

  setTimeout(() => {
    document.getElementById(id)?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }, 100);
}

// ============ ACERCA DE SIGAIRE ============
const workGroup = [
  "MTRA. NORMA ELSA REYES PIÑA",
  "DR. JESUS ALBERTO GARCIA ROJAS",
  "DR. OCTAVIO CATARINO AGUILAR",
];

const collaborators = [
  { name: "P.I.I IVAN DAVID GARCÍA", role: "" },
  { name: "I.I. MARIANA", role: "Visión artificial" },
  { name: "I.I. EDUARDO", role: "Arquitectura de robot móvil" },
  { name: "I.I. LIZETH JOSE ÁNGELES", role: "Visión artificial" },
  { name: "ADRIANA MARTINEZ RAYMUNDO", role: "" },
  { name: "JARED LÓPEZ LÓPEZ", role: "" },
];

const aboutFeatures = [
  "Tarjetas visuales y gráficos de fácil lectura en cualquier dispositivo.",
  "Mapa de precipitación con vista rápida y enlace a detalle.",
  "Consejos de salud y uso según humedad e índice UV.",
  "Navegación tipo pill con accesos a radar, contaminantes y alertas.",
];

const aboutSources = ["Tomorrow.io", "OpenStreetMap + Leaflet"];

const aboutTech = [
  { label: "Frontend", value: "Vue, diseño responsive propio." },
  { label: "Gráficos", value: "ECharts y componentes personalizados." },
  { label: "Mapas", value: "Leaflet." },
  { label: "Despliegue", value: "Vercel." },
  
];

// Iniciales para el avatar (se omiten los títulos: MTRA., DR., I.I., P.I.I)
function personInitials(name) {
  const clean = String(name)
    .replace(/^(MTRA\.|DR\.|P\.I\.I|I\.I\.)\s*/i, "")
    .trim();
  const words = clean.split(/\s+/).filter(Boolean);
  return (words[0]?.[0] || "") + (words[1]?.[0] || "");
}

function openAbout() {
  closeSensorDetail();
  showAbout.value = true;
  showHistory.value = false;
  menuOpen.value = false;
  settingsOpen.value = false;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function closeAbout() {
  showAbout.value = false;
}

function openAdminLogin() {
  loginOpen.value = true;
  settingsOpen.value = false;
  menuOpen.value = false;
}

function handleAdminLogin(data) {
  loginOpen.value = false;
  emit("admin", data);
}

</script>

<template>
  <div class="public-health-dashboard">
    <!-- ENCABEZADO -->
    <header class="public-header">
      <div class="header-left">
        <button
          class="menu-button"
          type="button"
          aria-label="Abrir menú"
          @click="menuOpen = !menuOpen"
        >
          <span></span>
          <span></span>
          <span></span>
        </button>

        <span class="logo-badge">
          <img
            class="header-logo"
            src="/Logo.png"
            alt="Logo del sistema"
          />
        </span>

        <div class="header-title">
          <h1>Sistema Inteligente de Gestión Autónoma de la Calidad del Aire</h1>
        </div>
      </div>

      <div class="header-right">
        <button
          class="settings-button"
          type="button"
          aria-label="Configuración"
          @click="settingsOpen = !settingsOpen"
        >
          <span>⚙</span>
        </button>
      </div>

      <!-- MENÚ PRINCIPAL -->
      <div
        class="menu-backdrop"
        :class="{ open: menuOpen }"
        @click="menuOpen = false"
      ></div>

      <aside
        class="navigation-drawer"
        :class="{ open: menuOpen }"
        aria-label="Menú de navegación"
      >
        <div class="drawer-header">
          <span class="drawer-logo">
            <img src="/Logo.png" alt="Logo" />
          </span>

          <div class="drawer-brand">
            <strong>SIGAIRE</strong>
            <span>Menú de navegación</span>
          </div>

          <button
            type="button"
            class="drawer-close"
            aria-label="Cerrar menú"
            @click="menuOpen = false"
          >
            ×
          </button>
        </div>

        <p class="drawer-section-label">Navegación</p>

        <nav>
          <button
            type="button"
            :class="{ active: !showHistory && !showAbout }"
            @click="goHome"
          >
            <span class="nav-icon">⌂</span>
            <span class="nav-text">
              <strong>Inicio</strong>
              <small>Panel general</small>
            </span>
            <span class="nav-arrow">›</span>
          </button>

          <button type="button" @click="scrollToId('sensores')">
            <span class="nav-icon">▦</span>
            <span class="nav-text">
              <strong>Sensores ambientales</strong>
              <small>Lecturas en tiempo real</small>
            </span>
            <span class="nav-arrow">›</span>
          </button>

          <button type="button" @click="scrollToId('ubicacion')">
            <span class="nav-icon">⌖</span>
            <span class="nav-text">
              <strong>Ubicación</strong>
              <small>Mapa de referencia</small>
            </span>
            <span class="nav-arrow">›</span>
          </button>

          <button
            type="button"
            :class="{ active: showHistory }"
            @click="openHistory"
          >
            <span class="nav-icon">◷</span>
            <span class="nav-text">
              <strong>Historial de monitoreo</strong>
              <small>Registros por fecha</small>
            </span>
            <span class="nav-arrow">›</span>
          </button>

          <button
            type="button"
            :class="{ active: showAbout }"
            @click="openAbout"
          >
            <span class="nav-icon">❖</span>
            <span class="nav-text">
              <strong>Acerca de SIGAIRE</strong>
              <small>Proyecto y equipo</small>
            </span>
            <span class="nav-arrow">›</span>
          </button>
        </nav>

        <div class="drawer-bottom">
          <button
            type="button"
            class="drawer-admin"
            @click="openAdminLogin"
          >
            <span class="nav-icon">♙</span>
            <span class="nav-text">
              <strong>Acceso de administrador</strong>
              <small>Panel técnico</small>
            </span>
            <span class="nav-arrow">›</span>
          </button>


          <div class="drawer-footer">
            SIGAIRE
          </div>
        </div>
      </aside>

      <!-- CONFIGURACIÓN -->
      <div v-if="settingsOpen" class="settings-popover">
        <div class="settings-heading">
          <strong>Información del sistema</strong>
          <button type="button" @click="settingsOpen = false">×</button>
        </div>


        <button
          class="admin-access-button"
          type="button"
          @click="openAdminLogin"
        >
          Acceso de administrador
        </button>
      </div>
    </header>

    <!-- VISTA PRINCIPAL -->
    <main v-if="!showHistory && !showAbout" class="public-dashboard-body">

      <!-- MAPA (1/4) -->
      <section id="ubicacion" class="location-panel">
        <div class="map-container">
          <iframe
            title="Mapa de ubicación del Tecnológico de Estudios Superiores de San Felipe del Progreso"
            src="https://maps.google.com/maps?q=Tecnol%C3%B3gico%20de%20Estudios%20Superiores%20de%20San%20Felipe%20del%20Progreso&t=&z=15&ie=UTF8&iwloc=&output=embed"
            loading="lazy"
            referrerpolicy="no-referrer-when-downgrade"
          ></iframe>

          <div class="map-badge">
            <span class="location-icon">⌖</span>
            <div>
              <span class="section-kicker">UBICACIÓN</span>
            </div>
          </div>
        </div>

        <div class="location-description">
          <span class="location-pin">⌖</span>
          <div>
            <strong>Tecnológico de San Felipe del Progreso</strong>
            <p>Ubicación de referencia del sistema.</p>
          </div>
        </div>
      </section>

      <!-- SENSORES (3/4) -->
      <section id="sensores" class="sensor-dashboard">
        <div class="sensor-dashboard-heading">
          <div>
            <span class="section-kicker">MONITOREO</span>
            <h2>Indicadores ambientales</h2>
            <p>Mediciones y orientación ambiental de cada sensor.</p>
          </div>

          <div class="sensor-count">
            <span class="count-dot"></span>
            6 sensores
          </div>
        </div>

        <div class="sensors-grid-3">
          <article
            v-for="card in allSensors"
            :key="card.id"
            class="card-wrapper public-metric-card sensor-summary-card"
            :class="[`tone-${card.tone}`, `card-${card.id}`, { active: selectedSensor?.id === card.id }]"
            role="button"
            tabindex="0"
            :aria-label="`Ver información de ${card.title}`"
            @pointerenter="hoverOpenSensor(card, $event)"
            @pointermove="tiltCard($event)"
            @pointerleave="onCardLeave(card, $event)"
            @click="pinSensor(card, $event)"
            @keydown.enter.prevent="pinSensorByKey(card, $event)"
            @keydown.space.prevent="pinSensorByKey(card, $event)"
            @keydown.esc="closeSensorDetail"
          >
            <div class="metric-card-top">
              <div class="metric-card-icon">
                <span v-if="card.iconType === 'pm25'">◉</span>
                <span v-else-if="card.iconType === 'pm10'">◌</span>
                <span v-else-if="card.iconType === 'co2'">CO₂</span>
                <span v-else-if="card.iconType === 'temp'">☼</span>
                <span v-else-if="card.iconType === 'sharp'">⚲</span>
                <span v-else>◈</span>
              </div>
              <span class="metric-source">{{ card.source }}</span>
            </div>

            <div class="metric-card-content">
              <h3>{{ card.title }}</h3>
              <p class="metric-subtitle">{{ card.description }}</p>
              <div class="metric-number-row">
                <strong>{{ card.value }}</strong>
                <span>{{ card.unit }}</span>
              </div>
              <div v-if="card.id === 'temperature'" class="humidity-value">
                Humedad: <strong>{{ card.humidity }} {{ card.humidityUnit }}</strong>
              </div>
              <div class="metric-status-row">
                <span class="status-indicator"></span>
                {{ card.emoji || "📡" }} {{ cleanCardStatus(card.status) }}
              </div>
              <div class="metric-progress">
                <i :style="{ width: `${card.percent}%` }"></i>
              </div>
            </div>

            <div class="sensor-summary-action">
              <span>Pasa el cursor o toca para ver información</span>
              <span aria-hidden="true">↗</span>
            </div>
          </article>
        </div>
      </section>
    </main>

    <!-- HISTORIAL -->
    <main v-else-if="showHistory" class="history-view">
      <div class="history-heading">
        <div>
          <span class="section-kicker">REGISTROS DEL SISTEMA</span>
          <h2>Historial de monitoreo</h2>
          <p>Consulta las mediciones almacenadas por fecha.</p>
        </div>

        <button type="button" class="back-button" @click="closeHistory">
          ← Regresar al inicio
        </button>
      </div>


      <section class="today-history-summary">
        <span class="today-history-icon">{{ todayHistorySummary.emoji }}</span>
        <div>
          <strong>Hoy · {{ todayDateLabel }}</strong>
          <p>{{ todayHistorySummary.label }}</p>
          <small>{{ todayHistorySummary.source }}</small>
        </div>
      </section>

      <div v-if="historyByDay.length" class="history-layout">
        <section class="history-panel">
          <h3>Fechas disponibles</h3>

          <div class="history-timeline">
            <button
              v-for="day in historyByDay"
              :key="day.date"
              type="button"
              class="history-date-item"
              :class="{ active: selectedHistory?.date === day.date }"
              @click="openHistoryDay(day)"
            >
              <span class="history-calendar-icon">{{ getDayCondition(day).emoji }}</span>

              <span>
                <strong>{{ formatHistoryDate(day.timestamp) }}</strong>
                <small>{{ getDayCondition(day).label }} · {{ day.records.length }} registro(s)</small>
              </span>

              <span class="history-chevron">›</span>
            </button>
          </div>
        </section>

        <section class="history-panel history-detail-panel">
          <template v-if="selectedHistory">
            <span class="section-kicker">DETALLE DEL REGISTRO</span>
            <h3>{{ getDayCondition(selectedHistory).emoji }} {{ formatHistoryDate(selectedHistory.timestamp) }}</h3>
            <p class="history-day-summary">{{ getDayCondition(selectedHistory).label }} · Cada tarjeta muestra el promedio del día y el rango mínimo–máximo de las lecturas disponibles. Se incluyen los sensores que hayan enviado datos.</p>

            <div class="history-values-grid">
              <div
                v-for="item in getHistoryValues(selectedHistory)"
                :key="item.label"
                class="history-value-card"
              >
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
                <small>{{ item.count }} lectura(s) · {{ item.unit || "—" }}</small>
              </div>
            </div>
          </template>

          <div v-else class="history-empty-selection">
            <span>◷</span>
            <h3>Selecciona una fecha</h3>
            <p>Elige uno de los días disponibles para consultar sus mediciones.</p>
          </div>
        </section>
      </div>

      <div v-else class="history-empty">
        <span>◷</span>
        <h3>No hay registros disponibles</h3>
        <p>Cuando se almacenen mediciones, aparecerán aquí organizadas por fecha.</p>
      </div>
    </main>

    <!-- ACERCA DE SIGAIRE -->
    <main v-else class="about-view">
      <div class="history-heading">
        <div>
          <span class="section-kicker">ACERCA DE NOSOTROS</span>
          <h2>Acerca de SIGAIRE</h2>
          <p>Conoce el proyecto, el equipo y las herramientas detrás del sistema.</p>
        </div>

        <button type="button" class="back-button" @click="closeAbout">
          ← Regresar al inicio
        </button>
      </div>

      <section class="about-hero">
        <span class="about-hero-logo">
          <img src="/Logo.png" alt="Logo de SIGAIRE" />
        </span>
        <div>
          <h3>SIGAIRE</h3>
          <strong>Sistema Inteligente de Gestión Autónoma de la Calidad del Aire</strong>
          <p>
            Es una aplicación web responsiva desarrollada en el Tecnológico de Estudios Superiores
            de San Felipe Progreso. Su objetivo es acercar indicadores ambientales claros y accionables
            para la comunidad académica y la población en general.
          </p>
        </div>
      </section>

      <div class="about-grid">
        <section class="about-card">
          <span class="about-icon">🎯</span>
          <h3>Propósito</h3>
          <p>
            Brindar información ambiental local, confiable y actualizada para apoyar la toma de
            decisiones cotidianas (salud, movilidad, actividades al aire libre) y fomentar la
            educación ambiental.
          </p>
        </section>

        <section class="about-card">
          <span class="about-icon">🗺️</span>
          <h3>Alcance</h3>
          <p>
            Visualización de calidad del aire (AQI).
          </p>
        </section>

        <section class="about-card">
          <span class="about-icon">🎓</span>
          <h3>Grupo de trabajo</h3>
          <ul class="about-people">
            <li v-for="person in workGroup" :key="person">
              <span class="about-avatar">{{ personInitials(person) }}</span>
              <strong>{{ person }}</strong>
            </li>
          </ul>
        </section>

        <section class="about-card">
          <span class="about-icon">🤝</span>
          <h3>Colaboradores</h3>
          <ul class="about-people">
            <li v-for="person in collaborators" :key="person.name">
              <span class="about-avatar">{{ personInitials(person.name) }}</span>
              <span>
                <strong>{{ person.name }}</strong>
                <small v-if="person.role">{{ person.role }}</small>
              </span>
            </li>
          </ul>
        </section>

        <section class="about-card about-wide">
          <span class="about-icon">✨</span>
          <h3>Características clave</h3>
          <ul class="about-checklist">
            <li v-for="feature in aboutFeatures" :key="feature">{{ feature }}</li>
          </ul>
        </section>

        <section class="about-card">
          <span class="about-icon">📡</span>
          <h3>Fuentes de datos</h3>
          <div class="about-chips">
            <span v-for="source in aboutSources" :key="source">{{ source }}</span>
          </div>
        </section>

        <section class="about-card">
          <span class="about-icon">🛠️</span>
          <h3>Tecnologías</h3>
          <dl class="about-tech">
            <div v-for="item in aboutTech" :key="item.label">
              <dt>{{ item.label }}</dt>
              <dd>{{ item.value }}</dd>
            </div>
          </dl>
        </section>

        <section class="about-card">
          <span class="about-icon">🔒</span>
          <h3>Privacidad</h3>
          <p>
            SIGAIRE no almacena datos personales sensibles. Las solicitudes a proveedores externos
            se realizan conforme a sus políticas. Pronto publicaremos nuestro aviso de privacidad.
          </p>
        </section>

        <section class="about-card">
          <span class="about-icon">♿</span>
          <h3>Accesibilidad</h3>
          <p>
            Mantenemos contraste adecuado, semántica HTML y navegación por teclado. Si detectas
            barreras, háznoslo saber para corregirlas.
          </p>
        </section>

        <section class="about-card">
          <span class="about-icon">✉️</span>
          <h3>Contacto</h3>
          <p>Para dudas, sugerencias o colaboración:</p>
          <a class="about-mail" href="mailto:contacto@sigaire.edu.mx">contacto@sigaire.edu.mx</a>
        </section>

        <section class="about-card">
          <span class="about-icon">💚</span>
          <h3>Agradecimientos</h3>
          <p>
            A la comunidad del TESFTP de San Felipe Progreso y a los proyectos Tomorrow.io,
            OpenStreetMap y Leaflet por sus herramientas abiertas y documentación.
          </p>
        </section>
      </div>
    </main>

    <!-- VENTANA DE INFORMACIÓN DEL SENSOR -->
    <Transition name="sensor-pop">
      <div
        v-if="selectedSensor"
        class="sensor-modal-backdrop"
        :class="{ 'hover-mode': sensorModalMode === 'hover' }"
        role="presentation"
        @click.self="closeSensorDetail"
      >
        <section
          class="sensor-modal-window"
          :class="[`modal-${selectedSensor.id}`, { 'is-pinned': sensorModalMode === 'pinned' }]"
          :style="{ '--from-x': sensorOrigin.x + 'px', '--from-y': sensorOrigin.y + 'px' }"
          role="dialog"
          aria-modal="true"
          :aria-label="`Detalles de ${selectedSensor.title}`"
          @pointerenter="sensorWindowEnter"
          @pointerleave="sensorWindowLeave"
          @keydown.esc="closeSensorDetail"
        >
          <button
            v-if="sensorModalMode === 'pinned'"
            class="sensor-modal-close"
            type="button"
            aria-label="Cerrar"
            @click="closeSensorDetail"
          >×</button>

          <header class="sensor-modal-heading">
            <div class="sensor-modal-title-block">
              <span class="sensor-modal-emoji" aria-hidden="true">{{ selectedSensor.emoji || "📡" }}</span>
              <div>
                <span class="sensor-modal-kicker">MONITOREO AMBIENTAL</span>
                <h2>{{ selectedSensor.title }}</h2>
                <p>{{ selectedSensor.source }}</p>
              </div>
            </div>

            <div class="sensor-modal-reading">
              <strong>{{ selectedSensor.value }} <small>{{ selectedSensor.unit }}</small></strong>
              <em><i class="sensor-modal-dot" :class="`dot-${selectedSensor.tone}`"></i>{{ cleanCardStatus(selectedSensor.status) }}</em>
              <small v-if="selectedSensor.id === 'temperature'">
                Humedad: {{ selectedSensor.humidity }} {{ selectedSensor.humidityUnit }}
              </small>
            </div>
          </header>

          <div class="sensor-modal-content">
            <div class="sensor-info-grid">
              <section class="sensor-info-section sensor-info-card">
                <span class="sensor-info-icon">📡</span>
                <div class="sensor-info-body">
                  <span class="sensor-info-kicker">CONOCE EL SENSOR</span>
                  <h4>¿Qué mide?</h4>
                  <p>{{ selectedSensor.detail }}</p>
                </div>
              </section>

              <section class="sensor-info-section sensor-info-card">
                <span class="sensor-info-icon">🔎</span>
                <div class="sensor-info-body">
                  <span class="sensor-info-kicker">EN EL ENTORNO</span>
                  <h4>Fuentes comunes</h4>
                  <p>{{ sensorEnvironmentExamples(selectedSensor.id) }}</p>
                </div>
              </section>
            </div>

            <section class="sensor-info-section sensor-advice-section">
              <span class="sensor-info-icon">💡</span>
              <div class="sensor-info-body">
                <span class="sensor-info-kicker">CONSEJO PRÁCTICO</span>
                <h4>Recomendación</h4>
                <p>{{ sensorRecommendation(selectedSensor) }}</p>
              </div>
            </section>

            <p class="sensor-card-footnote">
              Orientación informativa basada en la lectura recibida. Los tramos mostrados no sustituyen
              un promedio normativo ni un diagnóstico sanitario. Las señales analógicas en voltios
              requieren calibración para convertirse en concentraciones.
            </p>
          </div>
        </section>
      </div>
    </Transition>

    <footer class="public-footer">
      <span>SIGAIRE · Sistema Inteligente de Gestión Autónoma de la Calidad del Aire</span>
      <span>Monitoreo de calidad del aire.</span>
    </footer>

    <!-- INICIO DE SESIÓN DE ADMINISTRADOR -->
    <AdminLogin
      v-if="loginOpen"
      @close="loginOpen = false"
      @success="handleAdminLogin"
    />
  </div>
</template>

<style scoped>
* {
  box-sizing: border-box;
}

.public-health-dashboard {
  min-height: 100vh;
  width: 100vw;
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(circle at 100% 0%, #fcf1fa 0, transparent 38%),
    radial-gradient(circle at 0% 100%, #f8e5f5 0, transparent 32%),
    #f8f5f8;
  color: #422b43;
  font-family: Inter, "Segoe UI", Arial, sans-serif;
  overflow-x: hidden;
}

/* ============ ENCABEZADO ============ */

.public-header {
  position: relative;
  z-index: 20;
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 66px;
  width: 100vw;
  margin-left: calc(-50vw + 50%);
  margin-right: calc(-50vw + 50%);
  padding: 8px 3% 10px;
  background: #912648;
  border-radius: 0 0 22px 22px;
  box-shadow: 0 10px 28px rgba(145, 38, 72, 0.28);
  flex-shrink: 0;
}

.public-header::after {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background:
    radial-gradient(circle at 88% -30%, rgba(255, 255, 255, 0.16) 0, transparent 40%),
    radial-gradient(circle at 20% 140%, rgba(255, 255, 255, 0.1) 0, transparent 45%);
  pointer-events: none;
}

.header-left,
.header-right {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 12px;
}

.menu-button,
.settings-button {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 38px;
  height: 38px;
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.16);
  color: #ffffff;
  cursor: pointer;
  transition: background 0.2s;
}

.menu-button:hover,
.settings-button:hover {
  background: rgba(255, 255, 255, 0.28);
}

.menu-button {
  flex-direction: column;
  gap: 5px;
}

.menu-button span {
  display: block;
  width: 16px;
  height: 2px;
  border-radius: 5px;
  background: #ffffff;
}

.settings-button {
  font-size: 19px;
}

.logo-badge {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: #ffffff;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.16);
  flex-shrink: 0;
}

.header-logo {
  width: 42px;
  height: 42px;
  object-fit: contain;
}

.header-title h1 {
  margin: 0;
  max-width: 760px;
  color: #ffffff;
  font-size: 15px;
  font-weight: 800;
  line-height: 1.25;
}

.header-title > span {
  display: inline-block;
  margin-top: 6px;
  padding: 3px 12px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.16);
  color: #f7d6e2;
  font-size: 12px;
  font-weight: 700;
}

.connection-indicator {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 10px 16px;
  border-radius: 30px;
  background: rgba(255, 255, 255, 0.15);
  color: #f7d6e2;
  font-size: 13px;
  font-weight: 700;
  backdrop-filter: blur(5px);
}

.connection-indicator.connected {
  background: rgba(22, 141, 117, 0.4);
  color: #eaf8f3;
}

.connection-dot,
.count-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #f7d6e2;
}

.connected .connection-dot,
.count-dot {
  background: #20aa91;
  box-shadow: 0 0 0 4px rgba(32, 170, 145, 0.22);
}

/* ============ MENÚ LATERAL ============ */

.menu-backdrop {
  position: fixed;
  z-index: 30;
  inset: 0;
  background: rgba(35, 20, 35, 0.4);
  backdrop-filter: blur(3px);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.25s ease;
}

.menu-backdrop.open {
  opacity: 1;
  pointer-events: auto;
}

.navigation-drawer {
  position: fixed;
  z-index: 31;
  top: 0;
  bottom: 0;
  left: 0;
  display: flex;
  flex-direction: column;
  width: 400px;
  max-width: 92vw;
  padding: 22px 20px 20px;
  overflow-y: auto;
  background: #fff;
  border-radius: 0 32px 32px 0;
  box-shadow: 15px 0 45px rgba(45, 20, 45, 0.2);
  transform: translateX(-110%);
  visibility: hidden;
  transition: transform 0.3s ease, visibility 0s linear 0.3s;
}

.navigation-drawer.open {
  transform: translateX(0);
  visibility: visible;
  transition: transform 0.3s ease, visibility 0s;
}

/* Cabecera del menú con el color institucional */

.drawer-header {
  position: relative;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px;
  overflow: hidden;
  border-radius: 24px;
  background: #912648;
  box-shadow: 0 8px 20px rgba(145, 38, 72, 0.28);
}

.drawer-header::after {
  content: "";
  position: absolute;
  top: -50px;
  right: -40px;
  width: 140px;
  height: 140px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.12);
  pointer-events: none;
}

.drawer-logo {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  width: 64px;
  height: 64px;
  flex-shrink: 0;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.18);
}

.drawer-logo img {
  width: 48px;
  height: 48px;
  object-fit: contain;
}

.drawer-brand {
  position: relative;
  z-index: 1;
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 4px;
}

.drawer-brand strong {
  color: #fff;
  font-size: 22px;
  font-weight: 900;
  letter-spacing: 1px;
}

.drawer-brand span {
  color: #f7d6e2;
  font-size: 13px;
  font-weight: 700;
}

.drawer-close {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  width: 40px;
  height: 40px;
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.18);
  color: #fff;
  font-size: 26px;
  line-height: 1;
  cursor: pointer;
  transition: background 0.2s;
}

.drawer-close:hover {
  background: rgba(255, 255, 255, 0.32);
}

.drawer-section-label {
  margin: 26px 0 10px 12px;
  color: #987b98;
  font-size: 13px;
  font-weight: 800;
}

/* Elementos de navegación */

.navigation-drawer nav {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.navigation-drawer nav button,
.drawer-admin {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  padding: 12px 14px 12px 12px;
  border: 0;
  border-radius: 22px;
  background: transparent;
  color: #421e44;
  text-align: left;
  cursor: pointer;
  transition: background 0.2s, color 0.2s, transform 0.2s, box-shadow 0.2s;
}

.navigation-drawer nav button:hover,
.drawer-admin:hover {
  background: #fcf1fa;
  transform: translateX(4px);
}

.navigation-drawer nav button:focus-visible,
.drawer-admin:focus-visible,
.drawer-close:focus-visible {
  outline: 3px solid #b83299;
  outline-offset: 2px;
}

.nav-icon {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 46px;
  height: 46px;
  flex-shrink: 0;
  border-radius: 50%;
  background: #f8e5f5;
  color: #b83299;
  font-size: 22px;
  transition: background 0.2s, color 0.2s;
}

.nav-text {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.nav-text strong {
  color: #351237;
  font-size: 16px;
  font-weight: 850;
  line-height: 1.25;
}

.nav-text small {
  color: #7a5c7c;
  font-size: 13px;
  font-weight: 650;
}

.nav-arrow {
  color: #c34baa;
  font-size: 26px;
  line-height: 1;
  transition: transform 0.2s;
}

.navigation-drawer nav button:hover .nav-arrow,
.drawer-admin:hover .nav-arrow {
  transform: translateX(3px);
}

/* Elemento activo */

.navigation-drawer nav button.active {
  background: linear-gradient(110deg, #912648, #b83299);
  box-shadow: 0 8px 20px rgba(145, 38, 72, 0.28);
}

.navigation-drawer nav button.active .nav-icon {
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
}

.navigation-drawer nav button.active .nav-text strong {
  color: #fff;
}

.navigation-drawer nav button.active .nav-text small {
  color: #f7d6e2;
}

.navigation-drawer nav button.active .nav-arrow {
  color: #fff;
}

/* Parte inferior: administrador, estado y pie */

.drawer-bottom {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: auto;
  padding-top: 22px;
}

.drawer-admin {
  border: 2px dashed #dcbfd9;
  background: #fff;
}

.drawer-admin:hover {
  border-color: #b83299;
}

.drawer-status {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 18px;
  border-radius: 40px;
  background: #f8f5f8;
  color: #7a5c7c;
  font-size: 14px;
  font-weight: 800;
}

.drawer-status .connection-dot {
  background: #987b98;
}

.drawer-status.connected {
  background: #eaf8f3;
  color: #17967f;
}

.drawer-status.connected .connection-dot {
  background: #20aa91;
  box-shadow: 0 0 0 4px rgba(32, 170, 145, 0.22);
}

.drawer-footer {
  padding: 10px 8px 0;
  border-top: 2px solid #f0e4ef;
  color: #912648;
  font-size: 14px;
  font-weight: 900;
  letter-spacing: 1px;
  text-align: center;
}

.settings-popover {
  position: absolute;
  z-index: 40;
  top: 58px;
  right: 25px;
  width: 300px;
  padding: 20px;
  border: 1px solid #ead6e8;
  border-radius: 22px;
  background: #fff;
  box-shadow: 0 14px 36px rgba(65, 30, 65, 0.18);
}

.settings-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  color: #502c51;
  font-size: 14px;
}

.settings-heading button {
  border: 0;
  background: transparent;
  color: #b83299;
  font-size: 22px;
  cursor: pointer;
}

.setting-line {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 11px 0;
  border-top: 1px solid #f1e7f0;
  color: #806c83;
  font-size: 12px;
}

.setting-line strong {
  color: #502c51;
  text-align: right;
}

.text-good {
  color: #20aa91 !important;
}

.text-danger {
  color: #df657a !important;
}

.admin-access-button {
  width: 100%;
  margin-top: 12px;
  padding: 12px;
  border: 0;
  border-radius: 30px;
  background: #b83299;
  color: white;
  font-weight: 750;
  cursor: pointer;
}

/* ============ DISTRIBUCIÓN PRINCIPAL ============ */

.public-dashboard-body {
  display: grid;
  grid-template-columns: minmax(320px, 1fr) minmax(0, 3fr);
  align-items: stretch;
  gap: 24px;
  width: 100vw;
  max-width: 100vw;
  flex: 1;
  margin: 0;
  padding: 26px 2% 20px;
  overflow: hidden;
}

/* ============ MAPA ============ */

.location-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: 100%;
  width: 100%;
  padding: 12px;
  border-radius: 28px;
  background: #fff;
  box-shadow: 0 10px 32px rgba(84, 32, 77, 0.1);
}

.map-container {
  position: relative;
  width: 100%;
  flex: 1;
  min-height: 400px;
  overflow: hidden;
  border-radius: 20px;
  background: #f5edf5;
}

.map-container iframe {
  display: block;
  width: 100%;
  height: 100%;
  border: 0;
}

.map-badge {
  position: absolute;
  top: 14px;
  left: 14px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 18px 8px 8px;
  border-radius: 40px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 6px 18px rgba(84, 32, 77, 0.18);
  backdrop-filter: blur(6px);
}

.map-badge h2 {
  margin: 0;
  color: #351237;
  font-size: 18px;
  font-weight: 800;
  line-height: 1.1;
}

.section-kicker {
  display: block;
  margin-bottom: 4px;
  color: #b83299;
  font-size: 12px;
  font-weight: 850;
  letter-spacing: 1px;
}

.location-icon {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: #f8e5f5;
  color: #b83299;
  font-size: 23px;
  flex-shrink: 0;
}

.location-description {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  border-radius: 20px;
  background: #fcf1fa;
  flex-shrink: 0;
}

.location-pin {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: #fff;
  color: #b83299;
  font-size: 23px;
  flex-shrink: 0;
}

.location-description strong {
  display: block;
  color: #351237;
  font-size: 15px;
  line-height: 1.4;
  font-weight: 750;
}

.location-description p {
  margin: 4px 0 0;
  color: #553357;
  font-size: 14px;
  line-height: 1.4;
  font-weight: 600;
}

/* ============ SENSORES ============ */

.sensor-dashboard {
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  height: 100%;
  gap: 16px;
  width: 100%;
  min-width: 0;
}

.sensor-dashboard-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 15px;
  padding: 4px 6px 0;
  flex-shrink: 0;
}

.sensor-dashboard-heading h2,
.history-heading h2 {
  margin: 0;
  color: #351237;
  font-size: 30px;
  font-weight: 850;
  line-height: 1.15;
}

.sensor-dashboard-heading p {
  margin: 6px 0 0;
  max-width: 640px;
  color: #421e44;
  font-size: 15px;
  font-weight: 600;
}

.sensor-count {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  border-radius: 30px;
  background: #fff;
  box-shadow: 0 4px 14px rgba(84, 32, 77, 0.1);
  color: #351237;
  font-size: 14px;
  font-weight: 800;
  white-space: nowrap;
}

.sensors-grid-3 {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  align-content: start;
  align-items: stretch;
  gap: 14px;
  width: 100%;
  flex: 1;
}

.card-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* TARJETA: franja superior de color según estado, número protagonista */

.public-metric-card {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  width: 100%;
  height: 100%;
  min-width: 0;
  padding: 16px 18px 12px;
  border: 0;
  border-radius: 20px;
  background: #fff;
  box-shadow: 0 8px 26px rgba(84, 32, 77, 0.09);
  text-align: left;
  cursor: pointer;
  overflow: hidden;
  transition: transform 0.18s ease-out, box-shadow 0.25s ease;
}

.public-metric-card::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 5px;
  background: linear-gradient(90deg, var(--s1, #c33da6), var(--s2, #d64bb5));
}

.public-metric-card::after {
  content: "";
  position: absolute;
  top: -50px;
  right: -50px;
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background: var(--s-soft, #fcf1fa);
  z-index: 0;
}

.public-metric-card > * {
  position: relative;
  z-index: 1;
}


.public-metric-card:hover,
.public-metric-card.active {
  transform: perspective(900px) rotateX(var(--rx, 0deg)) rotateY(var(--ry, 0deg)) translateY(-5px);
  box-shadow: 0 16px 34px rgba(189, 59, 155, 0.2);
  box-shadow: 0 16px 34px color-mix(in srgb, var(--s1, #bd3b9b) 30%, transparent);
}

.metric-card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.metric-card-icon {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--s-soft, #f8e5f5);
  color: var(--s1, #b83299);
  font-size: 18px;
  font-weight: 900;
}

.metric-source {
  padding: 3px 10px;
  border-radius: 20px;
  background: #fff;
  box-shadow: 0 2px 8px rgba(84, 32, 77, 0.1);
  color: var(--s1, #911c79);
  font-size: 12px;
  font-weight: 900;
  text-align: right;
}

.metric-card-content {
  margin-top: 8px;
}

.metric-card-content h3 {
  margin: 0;
  color: #2a0c2c;
  font-size: 17px;
  font-weight: 900;
  line-height: 1.3;
}

.metric-subtitle {
  min-height: 0;
  margin: 6px 0 0;
  color: #4f2a51;
  font-size: 12.5px;
  line-height: 1.4;
  font-weight: 700;
}

.metric-number-row {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: auto;
  padding: 8px 0 4px;
}

.metric-number-row strong {
  color: var(--s1, #801368);
  font-size: clamp(30px, 2.6vw, 40px);
  font-weight: 900;
  line-height: 1;
  letter-spacing: -1px;
}

.metric-number-row > span {
  color: #421e44;
  font-size: 15px;
  font-weight: 850;
}

.humidity-value {
  display: inline-block;
  margin: 0 0 6px;
  padding: 2px 10px;
  border-radius: 20px;
  background: var(--s-soft, #fcf1fa);
  color: #421e44;
  font-size: 12.5px;
  font-weight: 800;
}

.humidity-value strong {
  color: var(--s1, #801368);
  font-size: 14px;
}

.metric-card-bottom {
  margin-top: 8px;
}

.metric-status-row {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 3px 10px 3px 8px;
  border-radius: 20px;
  background: #f8f5f8;
  color: #2a0c2c;
  font-size: 12.5px;
  font-weight: 850;
}

.status-indicator {
  width: 9px;
  height: 9px;
  flex-shrink: 0;
  border-radius: 50%;
  background: #987b98;
}

.tone-good .status-indicator {
  background: #17967f;
}

.tone-warning .status-indicator {
  background: #d48b26;
}

.tone-danger .status-indicator {
  background: #c7485e;
}

.metric-progress {
  width: 100%;
  height: 6px;
  margin-top: 8px;
  overflow: hidden;
  border-radius: 10px;
  background: #f0e4ef;
}

.metric-progress i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: #c33da6;
  transition: width 0.3s ease;
}

.tone-good .metric-progress i {
  background: #17967f;
}

.tone-warning .metric-progress i {
  background: #d48b26;
}

.tone-danger .metric-progress i {
  background: #c7485e;
}



.recommendation-strip {
  display: flex;
  align-items: center;
  gap: 22px;
  padding: 22px 28px 22px 24px;
  border-left: 10px solid #d64bb5;
  border-radius: 22px;
  background: #fdf2fb;
  box-shadow: 0 8px 24px rgba(189, 59, 155, 0.14);
  flex-shrink: 0;
  margin-top: auto;
}

.recommendation-symbol {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 60px;
  height: 60px;
  flex-shrink: 0;
  border-radius: 50%;
  background: #f5dff1;
  color: #b83299;
  font-size: 28px;
}

.recommendation-content {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.recommendation-label {
  color: #b83299;
  font-size: 15px;
  font-weight: 850;
  letter-spacing: 1.2px;
}

.recommendation-strip h3 {
  margin: 0;
  color: #2a0c2c;
  font-size: 26px;
  font-weight: 900;
}

.recommendation-strip p {
  margin: 0;
  color: #351237;
  font-size: 20px;
  line-height: 1.4;
  font-weight: 800;
}

.recommendation-warning {
  border-left-color: #e09b3a;
  background: #fffaf0;
}

.recommendation-warning .recommendation-symbol {
  background: #fff0d7;
  color: #d18a2e;
}

.recommendation-warning .recommendation-label {
  color: #c4862d;
}

.recommendation-danger {
  border-left-color: #df657a;
  background: #fff4f5;
}

.recommendation-danger .recommendation-symbol {
  background: #fbe3e7;
  color: #d45d73;
}

.recommendation-danger .recommendation-label {
  color: #d45d73;
}

.sensors-grid-3 > .sensor-summary-card {
  height: auto;
}

/* Cada tarjeta usa el mismo color que su ventana de información */
.card-pm25        { --s1: #8e1f6e; --s2: #d6459f; --s-soft: #fdf0f8; }
.card-pm10        { --s1: #1c4fa3; --s2: #3f8fe6; --s-soft: #eef5fe; }
.card-mg811       { --s1: #0b6b78; --s2: #20b2c2; --s-soft: #ebf9fb; }
.card-co2         { --s1: #2c7a3a; --s2: #5cc06b; --s-soft: #eff9f0; }
.card-temperature { --s1: #c2410c; --s2: #f59a2b; --s-soft: #fff4e8; }
.card-sharp       { --s1: #3b3aa3; --s2: #7f7cf0; --s-soft: #f1f0fe; }
.card-bfs         { --s1: #3a4a63; --s2: #7390b3; --s-soft: #eff3f8; }

/* ============ HISTORIAL ============ */

.history-view {
  width: 100%;
  min-height: calc(100vh - 145px);
  padding: 30px 3%;
}

.history-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  margin-bottom: 26px;
}

.history-heading p {
  margin: 8px 0 0;
  color: #987b98;
  font-size: 14px;
}

.back-button {
  padding: 12px 22px;
  border: 0;
  border-radius: 30px;
  background: #fff;
  box-shadow: 0 4px 14px rgba(84, 32, 77, 0.12);
  color: #a82d91;
  font-size: 14px;
  font-weight: 800;
  cursor: pointer;
}

.history-layout {
  display: grid;
  grid-template-columns: minmax(260px, 0.8fr) minmax(0, 2fr);
  gap: 22px;
}

.history-panel {
  min-width: 0;
  padding: 24px;
  border-radius: 26px;
  background: #fff;
  box-shadow: 0 8px 26px rgba(84, 32, 77, 0.09);
}

.history-panel > h3 {
  margin: 0 0 18px;
  color: #351237;
  font-size: 18px;
  font-weight: 850;
}

.history-timeline {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-left: 14px;
}

.history-timeline::before {
  content: "";
  position: absolute;
  top: 8px;
  bottom: 8px;
  left: 0;
  width: 3px;
  border-radius: 3px;
  background: #f0e4ef;
}

.history-date-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 14px 16px;
  border: 0;
  border-radius: 18px;
  background: #f8f5f8;
  text-align: left;
  cursor: pointer;
  transition: background 0.2s;
}

.history-date-item::before {
  content: "";
  position: absolute;
  left: -20px;
  top: 50%;
  width: 11px;
  height: 11px;
  border-radius: 50%;
  background: #fff;
  border: 3px solid #c33da6;
  transform: translateY(-50%);
}

.history-date-item.active,
.history-date-item:hover {
  background: #fcf1fa;
  box-shadow: inset 0 0 0 2px #d64bb5;
}

.history-calendar-icon {
  color: #b83299;
  font-size: 22px;
}

.history-date-item > span:nth-child(2) {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 5px;
}

.history-date-item strong {
  color: #351237;
  font-size: 13px;
  font-weight: 800;
}

.history-date-item small {
  color: #7a5c7c;
  font-size: 12px;
  font-weight: 600;
}

.history-chevron {
  color: #b83299;
  font-size: 22px;
}

.history-detail-panel {
  min-height: 300px;
}

.history-detail-panel h3 {
  margin: 5px 0 20px;
  color: #351237;
  font-size: 22px;
  font-weight: 850;
}

.history-values-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.history-value-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 20px;
  border-radius: 20px;
  background: #fcf5fb;
  border-bottom: 5px solid #c33da6;
}

.history-value-card span {
  color: #553357;
  font-size: 13px;
  font-weight: 700;
}

.history-value-card strong {
  color: #911c79;
  font-size: 30px;
  font-weight: 900;
}

.history-value-card small {
  color: #7a5c7c;
  font-size: 12px;
  font-weight: 700;
}

.history-empty-selection,
.history-empty {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  min-height: 280px;
  text-align: center;
}

.history-empty-selection > span,
.history-empty > span {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: #f8e5f5;
  color: #c34baa;
  font-size: 40px;
}

.history-empty-selection h3,
.history-empty h3 {
  margin: 14px 0 6px;
  color: #351237;
  font-size: 18px;
  font-weight: 850;
}

.history-empty-selection p,
.history-empty p {
  max-width: 380px;
  color: #7a5c7c;
  font-size: 13px;
  line-height: 1.6;
  font-weight: 600;
}

.history-empty {
  min-height: 400px;
  border: 2px dashed #dcbfd9;
  border-radius: 26px;
  background: #fff;
}

/* ============ PIE ============ */

.public-footer {
  display: flex;
  justify-content: space-between;
  gap: 15px;
  margin: 0 2% 18px;
  padding: 14px 26px;
  border-radius: 40px;
  background: #fff;
  box-shadow: 0 4px 16px rgba(84, 32, 77, 0.08);
  color: #7a5c7c;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}

/* Indicadores animados y detalle del historial */
.recommendation-animated {
  animation: recommendationPulse 2.2s ease-in-out infinite;
}
@keyframes recommendationPulse {
  0%, 100% { transform: scale(1) rotate(0deg); }
  50% { transform: scale(1.10) rotate(-4deg); }
}
.metric-status-row {
  display: flex;
  align-items: center;
  gap: 7px;
}
.history-day-summary {
  margin: -10px 0 18px;
  color: #7a5c7c;
  font-size: 13px;
  line-height: 1.5;
}
.recommendation-note {
  display: block;
  margin-top: 8px;
  color: #795a78;
  font-size: 11px;
  line-height: 1.45;
  font-weight: 600;
}
.history-value-card {
  min-width: 0;
  overflow-wrap: anywhere;
}
.history-value-card strong {
  font-size: clamp(19px, 2vw, 30px);
}
.history-date-item .history-calendar-icon {
  min-width: 30px;
  text-align: center;
  animation: historyFloat 3s ease-in-out infinite;
}
@keyframes historyFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-3px); }
}

/* ============ ACERCA DE SIGAIRE ============ */

.about-view {
  width: 100%;
  flex: 1;
  padding: 26px 3% 24px;
}

.about-hero {
  position: relative;
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 18px;
  padding: 22px 26px;
  overflow: hidden;
  border-radius: 24px;
  background: linear-gradient(120deg, #912648 0%, #b83299 100%);
  box-shadow: 0 10px 28px rgba(145, 38, 72, 0.25);
  color: #fff;
}

.about-hero::after {
  content: "";
  position: absolute;
  top: -70px;
  right: -50px;
  width: 200px;
  height: 200px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.12);
  pointer-events: none;
}

.about-hero > div {
  position: relative;
  z-index: 1;
}

.about-hero-logo {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  width: 78px;
  height: 78px;
  flex-shrink: 0;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.18);
}

.about-hero-logo img {
  width: 60px;
  height: 60px;
  object-fit: contain;
}

.about-hero h3 {
  margin: 0;
  font-size: 28px;
  font-weight: 900;
  letter-spacing: 1px;
}

.about-hero strong {
  display: block;
  margin-top: 2px;
  color: #f7d6e2;
  font-size: 15px;
  font-weight: 800;
}

.about-hero p {
  margin: 10px 0 0;
  max-width: 820px;
  font-size: 15px;
  line-height: 1.6;
  font-weight: 500;
}

.about-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.about-card {
  position: relative;
  min-width: 0;
  padding: 20px 22px 18px;
  overflow: hidden;
  border-radius: 20px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(84, 32, 77, 0.09);
}

.about-card::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 5px;
  background: linear-gradient(90deg, #912648, #c33da6);
}

.about-wide {
  grid-column: 1 / -1;
}

.about-icon {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 38px;
  height: 38px;
  margin-bottom: 8px;
  border-radius: 12px;
  background: #fcf1fa;
  font-size: 19px;
}

.about-card h3 {
  margin: 0 0 8px;
  color: #351237;
  font-size: 18px;
  font-weight: 850;
}

.about-card p {
  margin: 0;
  color: #4b384a;
  font-size: 14px;
  line-height: 1.65;
  font-weight: 500;
}

.about-people {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.about-people li {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 14px;
  background: #faf6fa;
}

.about-avatar {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  border-radius: 50%;
  background: linear-gradient(135deg, #912648, #c33da6);
  color: #fff;
  font-size: 12px;
  font-weight: 900;
}

.about-people strong {
  display: block;
  color: #351237;
  font-size: 13px;
  font-weight: 800;
  line-height: 1.35;
}

.about-people small {
  display: block;
  margin-top: 1px;
  color: #912648;
  font-size: 12px;
  font-weight: 700;
}

.about-checklist {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 22px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.about-checklist li {
  position: relative;
  padding-left: 26px;
  color: #4b384a;
  font-size: 14px;
  line-height: 1.55;
  font-weight: 500;
}

.about-checklist li::before {
  content: "✓";
  position: absolute;
  top: 1px;
  left: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #eaf8f3;
  color: #17967f;
  font-size: 11px;
  font-weight: 900;
}

.about-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.about-chips span {
  padding: 6px 14px;
  border-radius: 20px;
  background: #fcf1fa;
  color: #801368;
  font-size: 13px;
  font-weight: 800;
}

.about-tech {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 0;
}

.about-tech > div {
  display: flex;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px solid #f1e7f0;
}

.about-tech > div:last-child {
  border-bottom: 0;
}

.about-tech dt {
  min-width: 128px;
  color: #912648;
  font-size: 13px;
  font-weight: 850;
}

.about-tech dd {
  margin: 0;
  color: #4b384a;
  font-size: 13px;
  font-weight: 500;
}

.about-mail {
  display: inline-block;
  margin-top: 8px;
  padding: 8px 16px;
  border-radius: 24px;
  background: #b83299;
  color: #fff;
  font-size: 14px;
  font-weight: 800;
  text-decoration: none;
  transition: background 0.2s;
}

.about-mail:hover {
  background: #912648;
}

.about-mail:focus-visible {
  outline: 3px solid #b83299;
  outline-offset: 3px;
}

@media (max-width: 900px) {
  .about-grid,
  .about-checklist {
    grid-template-columns: 1fr;
  }

  .about-hero {
    flex-direction: column;
    align-items: flex-start;
  }
}

/* ============ RESPONSIVE ============ */

@media (max-width: 1200px) {
  .public-dashboard-body {
    grid-template-columns: 1fr;
    overflow-y: auto;
    height: auto;
  }

  .sensors-grid-3 {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    grid-template-rows: auto;
  }

}

@media (max-width: 700px) {
  .public-header {
    border-radius: 0 0 24px 24px;
  }

  .header-title h1 {
    font-size: 12px;
  }

  .sensors-grid-3 {
    grid-template-columns: 1fr;
    grid-template-rows: auto;
  }

  .history-layout {
    grid-template-columns: 1fr;
  }

  .history-values-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .public-footer {
    flex-direction: column;
    border-radius: 22px;
    padding: 15px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .history-date-item .history-calendar-icon,
  .recommendation-animated { animation: none; }
}
</style>


<style>
.sensor-summary-card {
  cursor: pointer;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.sensor-summary-card:focus-visible {
  outline: 3px solid #c33da6;
  outline-offset: 4px;
}
.sensor-summary-action {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: auto;
  padding-top: 8px;
  border-top: 1px solid rgba(145, 38, 72, .14);
  color: var(--s1, #a12680);
  font-size: 11px;
  font-weight: 900;
}

/* ===== Ventana de información: compacta, con color según el estado ===== */
.sensor-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 22px;
  background: rgba(35, 12, 34, .55);
  backdrop-filter: blur(4px);
}
/* Con mouse el fondo no intercepta el cursor, pero la ventana sí (se puede bajar con la rueda) */
.sensor-modal-backdrop.hover-mode {
  pointer-events: none;
  background: rgba(35, 12, 34, .32);
  backdrop-filter: blur(2px);
}
.sensor-modal-backdrop.hover-mode .sensor-modal-window {
  pointer-events: auto;
}

.sensor-modal-window {
  --tone-1: #912648;
  --tone-2: #b83299;
  --tone-soft: #fcf1fa;
  --tone-line: #efd4e7;
  --tone-text: #801368;
  position: relative;
  width: min(820px, 100%);
  max-height: 86vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 24px;
  background: #fff;
  box-shadow: 0 24px 70px rgba(24, 5, 25, .4);
}
/* Cada sensor tiene su propia paleta */
.sensor-modal-window.modal-pm25 {
  --tone-1: #8e1f6e; --tone-2: #d6459f;
  --tone-soft: #fdf0f8; --tone-line: #f2cde3; --tone-text: #8e1f6e;
}
.sensor-modal-window.modal-pm10 {
  --tone-1: #1c4fa3; --tone-2: #3f8fe6;
  --tone-soft: #eef5fe; --tone-line: #c8dcf5; --tone-text: #1c4fa3;
}
.sensor-modal-window.modal-mg811 {
  --tone-1: #0b6b78; --tone-2: #20b2c2;
  --tone-soft: #ebf9fb; --tone-line: #bfe7ed; --tone-text: #0b6b78;
}
.sensor-modal-window.modal-co2 {
  --tone-1: #2c7a3a; --tone-2: #5cc06b;
  --tone-soft: #eff9f0; --tone-line: #c7e8cb; --tone-text: #2c7a3a;
}
.sensor-modal-window.modal-temperature {
  --tone-1: #c2410c; --tone-2: #f59a2b;
  --tone-soft: #fff4e8; --tone-line: #f8d9b0; --tone-text: #b13a0a;
}
.sensor-modal-window.modal-sharp {
  --tone-1: #3b3aa3; --tone-2: #7f7cf0;
  --tone-soft: #f1f0fe; --tone-line: #d3d1f7; --tone-text: #3b3aa3;
}
.sensor-modal-window.modal-bfs {
  --tone-1: #3a4a63; --tone-2: #7390b3;
  --tone-soft: #eff3f8; --tone-line: #d0dae7; --tone-text: #3a4a63;
}

/* Punto que indica el estado de la lectura (verde, ámbar, rojo) */
.sensor-modal-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-right: 6px;
  border-radius: 50%;
  background: #fff;
  vertical-align: middle;
  box-shadow: 0 0 0 2px rgba(255, 255, 255, .35);
}
.sensor-modal-dot.dot-good { background: #8af2c9; }
.sensor-modal-dot.dot-warning { background: #ffd56b; }
.sensor-modal-dot.dot-danger { background: #ff9fae; }

.sensor-modal-close {
  position: absolute;
  top: 12px;
  right: 14px;
  z-index: 2;
  width: 34px;
  height: 34px;
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, .25);
  color: #fff;
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
}
.sensor-modal-close:hover {
  background: rgba(255, 255, 255, .4);
}

/* Franja compacta: título a la izquierda, lectura a la derecha */
.sensor-modal-heading {
  flex-shrink: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 14px 22px;
  background: linear-gradient(120deg, var(--tone-1) 0%, var(--tone-2) 100%);
  color: #fff;
}
.sensor-modal-window.is-pinned .sensor-modal-heading {
  padding-right: 58px;
}
.sensor-modal-title-block {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.sensor-modal-emoji {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 44px;
  height: 44px;
  flex-shrink: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, .22);
  font-size: 22px;
}
.sensor-modal-kicker {
  display: block;
  color: rgba(255, 255, 255, .8);
  font-size: 9px;
  font-weight: 900;
  letter-spacing: .09em;
}
.sensor-modal-heading h2 {
  margin: 1px 0 0;
  color: #fff;
  font-size: 20px;
  font-weight: 900;
  line-height: 1.2;
}
.sensor-modal-title-block p {
  margin: 1px 0 0;
  color: rgba(255, 255, 255, .85);
  font-size: 12px;
  font-weight: 700;
}
.sensor-modal-reading {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  flex-shrink: 0;
  padding: 7px 14px;
  border-radius: 14px;
  background: rgba(255, 255, 255, .2);
  text-align: right;
}
.sensor-modal-reading strong {
  color: #fff;
  font-size: 24px;
  font-weight: 900;
  line-height: 1.1;
}
.sensor-modal-reading strong small {
  font-size: 12px;
  font-weight: 800;
}
.sensor-modal-reading em {
  margin-top: 2px;
  color: #fff;
  font-size: 11px;
  font-style: normal;
  font-weight: 800;
}
.sensor-modal-reading > small {
  margin-top: 2px;
  color: rgba(255, 255, 255, .92);
  font-size: 11px;
  font-weight: 700;
}

/* Contenido: tarjetas de información */
.sensor-modal-content {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 20px 18px;
  overflow-y: auto;
  overscroll-behavior: contain;
  background: #faf6fa;
}
.sensor-info-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.sensor-modal-content .sensor-info-section {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid var(--tone-line);
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 4px 14px rgba(84, 32, 77, .07);
}
.sensor-modal-content .sensor-info-icon {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  border-radius: 12px;
  background: var(--tone-soft);
  font-size: 19px;
}
.sensor-info-body {
  min-width: 0;
}
.sensor-modal-content .sensor-info-kicker {
  display: block;
  color: var(--tone-text);
  font-size: 9px;
  font-weight: 900;
  letter-spacing: .08em;
}
.sensor-modal-content .sensor-info-section h4 {
  margin: 2px 0 4px;
  color: #2a0c2c;
  font-size: 15px;
  font-weight: 850;
}
.sensor-modal-content .sensor-info-section p {
  margin: 0;
  color: #4b384a;
  font-size: 13.5px;
  line-height: 1.55;
}
/* Recomendación destacada con el color del estado */
.sensor-modal-content .sensor-advice-section {
  border: 0;
  border-left: 6px solid var(--tone-2);
  background: var(--tone-soft);
  box-shadow: 0 4px 14px rgba(84, 32, 77, .07);
}
.sensor-modal-content .sensor-advice-section .sensor-info-icon {
  background: linear-gradient(135deg, var(--tone-1), var(--tone-2));
  color: #fff;
}
.sensor-modal-content .sensor-advice-section p {
  color: #2f2030;
  font-weight: 600;
}
.sensor-modal-content .sensor-card-footnote {
  margin: 0;
  padding: 0 4px;
  color: #8b7888;
  font-size: 10.5px;
  line-height: 1.5;
}

/* Animación de entrada y salida */
.sensor-pop-enter-active,
.sensor-pop-leave-active {
  transition: opacity .22s ease;
}
.sensor-pop-enter-active .sensor-modal-window {
  transition: transform .36s cubic-bezier(.2, .9, .25, 1), opacity .24s ease;
}
.sensor-pop-leave-active .sensor-modal-window {
  transition: transform .22s ease-in, opacity .18s ease;
}
.sensor-pop-enter-from,
.sensor-pop-leave-to {
  opacity: 0;
}
/* La ventana nace y regresa al centro de la tarjeta que la abrió */
.sensor-pop-enter-from .sensor-modal-window,
.sensor-pop-leave-to .sensor-modal-window {
  opacity: 0;
  transform: translate(var(--from-x, 0px), var(--from-y, 0px)) scale(.25);
}
@media (prefers-reduced-motion: reduce) {
  .sensor-pop-enter-active,
  .sensor-pop-leave-active,
  .sensor-pop-enter-active .sensor-modal-window,
  .sensor-pop-leave-active .sensor-modal-window { transition: none; }
}

@media (max-width: 700px) {
  .sensor-modal-backdrop { padding: 9px; }
  .sensor-modal-window { max-height: 92vh; border-radius: 20px; }
  .sensor-modal-heading { flex-wrap: wrap; padding: 12px 16px; }
  .sensor-modal-window.is-pinned .sensor-modal-heading { padding-right: 52px; }
  .sensor-modal-reading { width: 100%; flex-direction: row; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 8px; text-align: left; }
  .sensor-info-grid { grid-template-columns: 1fr; }
  .sensor-modal-content { padding: 12px 14px 16px; }
}
</style>