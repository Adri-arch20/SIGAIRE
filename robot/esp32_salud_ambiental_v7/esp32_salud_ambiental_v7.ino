#include <WiFi.h>
#include <WebServer.h>
#include <Wire.h>
#include <Adafruit_SHT31.h>
#include <math.h>
#include <Preferences.h>

// SALUD AMBIENTAL METEOBOT V7.2 - ESP32: motores + SHT3x + Sharp + BFS-302 + MG811 CO2
// Arduino IDE: core "esp32 by Espressif" 3.x; Adafruit SHT31 Library.
// IMPORTANTE: las salidas analogicas/digitales hacia ESP32 requieren <=3.3 V.
const char* ssid = "I.I";
const char* password = "Holaaa1234";
WebServer server(80);
bool servidorIniciado = false;
bool wifiAnterior = false;
unsigned long ultimoIntentoWiFi = 0;

// PINES ORIGINALES DE MOTORES: NO MODIFICAR SIN REVISAR PUENTE H
const int L_IN1_PIN = 4;
const int L_IN2_PIN = 17;
const int R_IN1_PIN = 27;
const int R_IN2_PIN = 13;
const int PWM_FREQ = 20000;
const int PWM_RES = 8;
const int VELOCIDAD_AVANCE = 145;
const int VELOCIDAD_GIRO = 120;
const unsigned long TIMEOUT_SEGURIDAD = 750;
unsigned long ultimaOrden = 0;
bool motoresActivos = false;
int pwmIzquierdoActual = 0;
int pwmDerechoActual = 0;

// IMPORTANTE: /motores aplica PWM real. La pagina SALUD AMBIENTAL muestra
// el comando aplicado, no RPM, velocidad ni posicion fisica medida.
// Seguridad: STOP al iniciar, perder WiFi o superar 750 ms sin orden.

// SENSOR SHT3X I2C
const int SDA_PIN = 21;
const int SCL_PIN = 22;
Adafruit_SHT31 sht31 = Adafruit_SHT31();
bool shtConectado = false;
float temperatura = NAN;
float humedad = NAN;
unsigned long ultimaLecturaSht = 0;
unsigned long ultimoIntentoSht = 0;

// SHARP: alimentacion a 5 V con divisor 10k + 10k en Vo -> GPIO34
const int SHARP_LED_PIN = 25;
const int SHARP_SENSOR_PIN = 34;
const float FACTOR_DIVISOR_SHARP = 2.0f;
unsigned long ultimaMuestraSharp = 0;
long sumaRawSharp = 0;
long sumaMvSharp = 0;
int minRawSharp = 4095;
int maxRawSharp = 0;
int nRawSharp = 0;
int nMvSharp = 0;
int ciclosSharp = 0;
float sharpRaw = NAN;
float sharpAdcMv = NAN;
float sharpVoV = NAN;
int sharpMinRaw = 0;
int sharpMaxRaw = 0;
bool sharpListo = false;
bool sharpAdcAlto = false;

// BFS-302: GPIO27 ESTA OCUPADO POR MOTOR, por eso usamos 32 y 33.
// Proteger AOUT y DOUT frente a niveles de 5V (dos divisores si hace falta).
const int BFS_AOUT_PIN = 32;
const int BFS_DOUT_PIN = 33;
const float FACTOR_DIVISOR_BFS = 2.0f; // divisor 10k / 10k
float bfsRaw = NAN;
float bfsAdcMv = NAN;
float bfsAoutV = NAN;
int bfsDout = -1;
bool bfsListo = false;
bool bfsRevisarADC = false;
unsigned long ultimaLecturaBfs = 0;
unsigned long ultimaImpresion = 0;

// MG811 OKY3352 CO2: fuente EXTERNA de 6 V; ESP32 por USB.
// AOUT -> 100k -> GPIO35 -> 100k -> GND (TIERRA COMUN).
// DOUT y TCM quedan sin conectar.
// Lectura real: voltaje. ppm SOLO tras calibrar con referencia NDIR.
const int MG811_AOUT_PIN = 35;
const float FACTOR_DIVISOR_MG811 = 2.0f;
const unsigned long INTERVALO_MG811_MS = 1000;
// No interpretar calentamiento/deriva como cambio ambiental de CO2.
// Umbrales experimentales, NO especificaciones del fabricante.
const unsigned long MG811_PRECALENTAMIENTO_MS = 20UL * 60UL * 1000UL;
const float MG811_UMBRAL_CAMBIO_AOUT_MV = 40.0f;
const int MG811_MUESTRAS_EVENTO = 3;
// Captura linea base automaticamente SOLO si cumple ventana estable + tiempo.
const bool MG811_AUTO_BASE = true;
const unsigned long INTERVALO_HISTORIAL_MS = 10000;
const int MG811_HISTORIAL_N = 60;  // 10 min aproximadamente
float mg811Historial[MG811_HISTORIAL_N] = {0};
int mg811HistorialN = 0;
int mg811HistorialPos = 0;
unsigned long ultimaLecturaMg811 = 0;
unsigned long ultimaMuestraHistorialMg811 = 0;
float mg811Raw = NAN;
float mg811AdcMv = NAN;
float mg811AoutV = NAN;
float mg811Ppm = NAN;
float mg811DerivaMv = NAN;
float mg811RangoMv = NAN;
bool mg811Listo = false;
bool mg811RevisarADC = false;
bool mg811Estable = false;
float mg811BaseAdcMv = NAN;      // Solo RAM; se renueva despues de reiniciar
float mg811DeltaAoutMv = NAN;
int mg811CuentaAumento = 0;
int mg811CuentaDisminucion = 0;
const char* mg811Evento = "SIN_BASE";
bool mg811ValidacionTercero = false;
float mg811ErrorValidacionPct = NAN;

Preferences mg811Memoria;
float mg811V1 = 0, mg811V2 = 0;
float mg811Ppm1 = 0, mg811Ppm2 = 0;
bool mg811TieneC1 = false, mg811TieneC2 = false;
String entradaSerialCo2;


String numeroOAsignarNull(float numero, int decimales) {
  return isfinite(numero) ? String(numero, decimales) : String("null");
}

void configurarMotores() {
  ledcAttach(L_IN1_PIN, PWM_FREQ, PWM_RES);
  ledcAttach(L_IN2_PIN, PWM_FREQ, PWM_RES);
  ledcAttach(R_IN1_PIN, PWM_FREQ, PWM_RES);
  ledcAttach(R_IN2_PIN, PWM_FREQ, PWM_RES);
}

void motorIzquierdo(int velocidad) {
  velocidad = constrain(velocidad, -255, 255);
  if (velocidad > 0) {
    ledcWrite(L_IN1_PIN, velocidad);
    ledcWrite(L_IN2_PIN, 0);
  } else if (velocidad < 0) {
    ledcWrite(L_IN1_PIN, 0);
    ledcWrite(L_IN2_PIN, -velocidad);
  } else {
    ledcWrite(L_IN1_PIN, 0);
    ledcWrite(L_IN2_PIN, 0);
  }
}

void motorDerecho(int velocidad) {
  velocidad = constrain(velocidad, -255, 255);
  if (velocidad > 0) {
    ledcWrite(R_IN1_PIN, velocidad);
    ledcWrite(R_IN2_PIN, 0);
  } else if (velocidad < 0) {
    ledcWrite(R_IN1_PIN, 0);
    ledcWrite(R_IN2_PIN, -velocidad);
  } else {
    ledcWrite(R_IN1_PIN, 0);
    ledcWrite(R_IN2_PIN, 0);
  }
}

void aplicarMotores(int izquierda, int derecha) {
  izquierda = constrain(izquierda, -255, 255);
  derecha = constrain(derecha, -255, 255);
  motorIzquierdo(izquierda);
  motorDerecho(derecha);
  pwmIzquierdoActual = izquierda;
  pwmDerechoActual = derecha;
  motoresActivos = izquierda != 0 || derecha != 0;
  ultimaOrden = millis();
}

void detener() {
  aplicarMotores(0, 0);
  motoresActivos = false;
}

void conectarSht() {
  ultimoIntentoSht = millis();
  shtConectado = sht31.begin(0x44) || sht31.begin(0x45);
  if (shtConectado) {
    sht31.heater(false);
    Serial.println("SHT3x conectado");
  } else {
    temperatura = NAN;
    humedad = NAN;
    Serial.println("SHT3x ausente: revisa VCC y SDA/SCL");
  }
}

void leerSht() {
  if (!shtConectado) {
    if (millis() - ultimoIntentoSht >= 10000) conectarSht();
    return;
  }
  if (millis() - ultimaLecturaSht < 2000) return;
  ultimaLecturaSht = millis();
  float t = NAN;
  float h = NAN;
  if (sht31.readBoth(&t, &h) && isfinite(t) && isfinite(h) && h >= 0 && h <= 100) {
    temperatura = t;
    humedad = h;
  } else {
    temperatura = NAN;
    humedad = NAN;
    shtConectado = false;
    ultimoIntentoSht = millis();
  }
}

void leerSharp() {
  // Un pulso y una sola conversion ADC cada >=10 ms.
  if (millis() - ultimaMuestraSharp < 10) return;
  ultimaMuestraSharp = millis();

  digitalWrite(SHARP_LED_PIN, LOW);
  delayMicroseconds(280);
  if ((ciclosSharp & 1) == 0) {
    int raw = analogRead(SHARP_SENSOR_PIN);
    sumaRawSharp += raw;
    minRawSharp = min(minRawSharp, raw);
    maxRawSharp = max(maxRawSharp, raw);
    nRawSharp++;
  } else {
    sumaMvSharp += analogReadMilliVolts(SHARP_SENSOR_PIN);
    nMvSharp++;
  }
  delayMicroseconds(40);
  digitalWrite(SHARP_LED_PIN, HIGH);

  ciclosSharp++;
  if (ciclosSharp < 50) return;

  sharpRaw = sumaRawSharp / (float)nRawSharp;
  sharpAdcMv = sumaMvSharp / (float)nMvSharp;
  sharpVoV = (sharpAdcMv / 1000.0f) * FACTOR_DIVISOR_SHARP;
  sharpMinRaw = minRawSharp;
  sharpMaxRaw = maxRawSharp;
  sharpAdcAlto = sharpAdcMv > 2500 || sharpRaw > 3800;
  sharpListo = true;

  sumaRawSharp = 0;
  sumaMvSharp = 0;
  minRawSharp = 4095;
  maxRawSharp = 0;
  nRawSharp = 0;
  nMvSharp = 0;
  ciclosSharp = 0;
}

void leerBfs() {
  if (millis() - ultimaLecturaBfs < 1000) return;
  ultimaLecturaBfs = millis();
  long raw = 0;
  long mv = 0;
  for (int i = 0; i < 8; i++) {
    raw += analogRead(BFS_AOUT_PIN);
    mv += analogReadMilliVolts(BFS_AOUT_PIN);
  }
  bfsRaw = raw / 8.0f;
  bfsAdcMv = mv / 8.0f;
  bfsAoutV = bfsAdcMv * FACTOR_DIVISOR_BFS / 1000.0f;
  bfsDout = digitalRead(BFS_DOUT_PIN);
  // Lecturas RAW 0 y milivoltios > 100 mV requieren revision.
  bfsRevisarADC = (bfsRaw < 1 && bfsAdcMv > 100) || bfsAdcMv > 2600;
  bfsListo = true;
}

// Mantiene la adquisicion no bloqueante; el watchdog de motores sigue activo.
void leerMg811() {
  const unsigned long ahora = millis();
  if (ahora - ultimaLecturaMg811 < INTERVALO_MG811_MS) return;
  ultimaLecturaMg811 = ahora;

  long sumaRaw = 0;
  long sumaMv = 0;
  // GPIO35 pertenece a ADC1, compatible con WiFi en ESP32 clasica.
  // Descartar una lectura al cambiar de canal ADC.
  analogRead(MG811_AOUT_PIN);
  for (int i = 0; i < 16; i++) {
    sumaRaw += analogRead(MG811_AOUT_PIN);
    sumaMv += analogReadMilliVolts(MG811_AOUT_PIN);
  }
  mg811Raw = sumaRaw / 16.0f;
  mg811AdcMv = sumaMv / 16.0f;
  mg811AoutV = mg811AdcMv * FACTOR_DIVISOR_MG811 / 1000.0f;
  // Cerca del extremo de rango o cero: revisar conexion y atenuacion.
  mg811RevisarADC = mg811Raw <= 1 || mg811AdcMv < 90 || mg811AdcMv > 1150;
  mg811Listo = true;

  if (ahora - ultimaMuestraHistorialMg811 >= INTERVALO_HISTORIAL_MS) {
    ultimaMuestraHistorialMg811 = ahora;
    mg811Historial[mg811HistorialPos] = mg811AdcMv;
    mg811HistorialPos = (mg811HistorialPos + 1) % MG811_HISTORIAL_N;
    if (mg811HistorialN < MG811_HISTORIAL_N) mg811HistorialN++;

    mg811Estable = false;
    mg811DerivaMv = NAN;
    mg811RangoMv = NAN;
    if (mg811HistorialN == MG811_HISTORIAL_N) {
      float vmin = mg811Historial[0], vmax = mg811Historial[0];
      float primero = 0, ultimo = 0;
      // Posicion apunta al dato mas antiguo cuando la ventana esta llena.
      for (int i = 0; i < MG811_HISTORIAL_N; i++) {
        const float v = mg811Historial[i];
        if (v < vmin) vmin = v;
        if (v > vmax) vmax = v;
      }
      for (int i = 0; i < 6; i++) {
        primero += mg811Historial[(mg811HistorialPos + i) % MG811_HISTORIAL_N];
        ultimo += mg811Historial[(mg811HistorialPos + MG811_HISTORIAL_N - 6 + i) % MG811_HISTORIAL_N];
      }
      mg811RangoMv = vmax - vmin;
      mg811DerivaMv = (ultimo - primero) / 6.0f;
      // Criterio EXPERIMENTAL, no especificacion del fabricante.
      mg811Estable = mg811RangoMv <= 5.0f && fabsf(mg811DerivaMv) <= 2.5f;
    }
  }

  // Detectar CAMBIOS DE VOLTAJE respecto a base estable, sin llamar
  // a esos cambios "CO2 detectado" antes de validar con NDIR.
  if (MG811_AUTO_BASE && !isfinite(mg811BaseAdcMv) &&
      ahora >= MG811_PRECALENTAMIENTO_MS && mg811Estable &&
      !mg811RevisarADC && !motoresActivos) {
    float suma = 0.0f;
    for (int i = 0; i < MG811_HISTORIAL_N; i++) suma += mg811Historial[i];
    mg811BaseAdcMv = suma / MG811_HISTORIAL_N;
    Serial.printf("MG811: linea base automatica=%.2f mV ADC (NO ppm)\n", mg811BaseAdcMv);
  }
  mg811DeltaAoutMv = NAN;
  if (!mg811Listo || mg811RevisarADC) {
    mg811Evento = "REVISION_ADC";
    mg811CuentaAumento = mg811CuentaDisminucion = 0;
  } else if (!isfinite(mg811BaseAdcMv)) {
    mg811Evento = "SIN_BASE";
    mg811CuentaAumento = mg811CuentaDisminucion = 0;
  } else {
    mg811DeltaAoutMv = (mg811AdcMv - mg811BaseAdcMv) * FACTOR_DIVISOR_MG811;
    if (mg811DeltaAoutMv >= MG811_UMBRAL_CAMBIO_AOUT_MV) {
      if (mg811CuentaAumento < MG811_MUESTRAS_EVENTO) mg811CuentaAumento++;
      mg811CuentaDisminucion = 0;
    } else if (mg811DeltaAoutMv <= -MG811_UMBRAL_CAMBIO_AOUT_MV) {
      if (mg811CuentaDisminucion < MG811_MUESTRAS_EVENTO) mg811CuentaDisminucion++;
      mg811CuentaAumento = 0;
    } else {
      mg811CuentaAumento = mg811CuentaDisminucion = 0;
    }
    if (mg811CuentaAumento >= MG811_MUESTRAS_EVENTO) {
      mg811Evento = "AUMENTO_SENAL";
    } else if (mg811CuentaDisminucion >= MG811_MUESTRAS_EVENTO) {
      mg811Evento = "DISMINUCION_SENAL";
    } else {
      mg811Evento = "SIN_CAMBIO_SIGNIFICATIVO";
    }
  }

  mg811Ppm = NAN;
  const bool calibrado = mg811TieneC1 && mg811TieneC2 &&
    mg811Ppm1 > 0 && mg811Ppm2 > 0 &&
    fabsf(mg811V2 - mg811V1) >= 10.0f &&
    fabsf(mg811Ppm2 - mg811Ppm1) >= 200.0f;
  if (calibrado && !mg811RevisarADC) {
    const float lo = min(mg811V1, mg811V2);
    const float hi = max(mg811V1, mg811V2);
    if (mg811AdcMv >= lo && mg811AdcMv <= hi) {
      const float f = (mg811AdcMv - mg811V1) / (mg811V2 - mg811V1);
      mg811Ppm = expf(logf(mg811Ppm1) + f * (logf(mg811Ppm2) - logf(mg811Ppm1)));
    }
  }
}

bool mg811Calibrado() {
  return mg811TieneC1 && mg811TieneC2 &&
    mg811Ppm1 > 0 && mg811Ppm2 > 0 &&
    fabsf(mg811V2 - mg811V1) >= 10.0f &&
    fabsf(mg811Ppm2 - mg811Ppm1) >= 200.0f;
}

const char* mg811Estado() {
  if (!mg811Listo) return "SIN_DATOS";
  if (mg811RevisarADC) return "REVISION_ADC";
  if (!mg811Calibrado()) return "SIN_CALIBRAR";
  if (!isfinite(mg811Ppm)) return "FUERA_RANGO";
  return mg811ValidacionTercero ? "ESTIMACION_VALIDADA_3_PUNTOS" : "ESTIMACION_PENDIENTE_VALIDACION";
}

// Estos comandos NO inventan una referencia: las ppm se deben medir
// con un instrumento NDIR independiente, en condiciones estables.
void procesarComandoCo2(String comando) {
  comando.trim();
  comando.toUpperCase();
  if (comando == "HELP_CO2") {
    Serial.println("HELP_CO2 / BASE_CO2 / RESET_BASE / C1 <ppm_NDIR> / C2 <ppm_NDIR> / VALIDAR_CO2 <ppm_NDIR> / RESET_CO2");
    Serial.println("BASE_CO2 guarda voltaje, NO ppm. C1/C2/VALIDAR requieren mediciones reales de NDIR.");
    return;
  }
  if (comando == "RESET_BASE") {
    mg811BaseAdcMv = NAN;
    mg811DeltaAoutMv = NAN;
    mg811Evento = "SIN_BASE";
    mg811CuentaAumento = mg811CuentaDisminucion = 0;
    Serial.println("MG811: base de voltaje borrada; ppm calibradas no afectadas");
    return;
  }
  if (comando == "RESET_CO2") {
    mg811Memoria.clear();
    mg811TieneC1 = mg811TieneC2 = false;
    mg811ValidacionTercero = false;
    mg811V1 = mg811V2 = mg811Ppm1 = mg811Ppm2 = 0;
    mg811Ppm = mg811ErrorValidacionPct = NAN;
    Serial.println("MG811: referencias de ppm borradas. Base electrica en RAM no afectada.");
    return;
  }
  if (comando == "BASE_CO2") {
    if (motoresActivos || !mg811Listo || mg811RevisarADC || !mg811Estable ||
        millis() < MG811_PRECALENTAMIENTO_MS) {
      Serial.println("MG811: STOP motores, esperar >=20 min ESP32 y ventana de 10 min estable");
      return;
    }
    float suma = 0.0f;
    for (int i = 0; i < MG811_HISTORIAL_N; i++) suma += mg811Historial[i];
    mg811BaseAdcMv = suma / MG811_HISTORIAL_N;
    mg811CuentaAumento = mg811CuentaDisminucion = 0;
    mg811Evento = "SIN_CAMBIO_SIGNIFICATIVO";
    Serial.printf("MG811: nueva linea base %.2f mV ADC / %.4f V AOUT estimada; NO ES ppm\n",
                  mg811BaseAdcMv, mg811BaseAdcMv * FACTOR_DIVISOR_MG811 / 1000.0f);
    return;
  }
  bool c1 = comando.startsWith("C1 ");
  bool c2 = comando.startsWith("C2 ");
  bool validar = comando.startsWith("VALIDAR_CO2 ");
  if (!c1 && !c2 && !validar) {
    if (comando.length()) Serial.println("MG811: comando desconocido. Escribe HELP_CO2");
    return;
  }
  if (motoresActivos || !mg811Listo || mg811RevisarADC || !mg811Estable ||
      millis() < MG811_PRECALENTAMIENTO_MS) {
    Serial.println("MG811: no registrar ppm: STOP, >=20 min y 10 min estable requeridos");
    return;
  }
  if ((c2 && !mg811TieneC1) || (validar && !mg811Calibrado())) {
    Serial.println("MG811: primero C1 y C2 con referencias NDIR independientes");
    return;
  }
  String textoPpm = comando.substring(validar ? 12 : 3);
  textoPpm.trim();
  if (textoPpm.length() == 0) {
    Serial.println("MG811: falta concentracion NDIR");
    return;
  }
  bool punto = false;
  for (size_t i = 0; i < textoPpm.length(); i++) {
    char c = textoPpm.charAt(i);
    if (c == '.') {
      if (punto) { Serial.println("MG811: numero invalido"); return; }
      punto = true;
    } else if (c < '0' || c > '9') {
      Serial.println("MG811: referencia no numerica"); return;
    }
  }
  const float referencia = textoPpm.toFloat();
  if (!isfinite(referencia) || referencia < 200 || referencia > 10000) {
    Serial.println("MG811: referencia fuera de 200-10000 ppm");
    return;
  }
  // Captura la ultima conversion, sin pausas que interrumpan watchdog de motores.
  const float adcMv = mg811AdcMv;
  if (c1) {
    mg811V1 = adcMv;
    mg811Ppm1 = referencia;
    mg811TieneC1 = true;
    mg811TieneC2 = false;
    mg811ValidacionTercero = false;
    mg811ErrorValidacionPct = NAN;
    mg811Ppm = NAN;
    mg811Memoria.putFloat("v1", mg811V1);
    mg811Memoria.putFloat("p1", mg811Ppm1);
    mg811Memoria.putBool("c1", true);
    mg811Memoria.putBool("c2", false);
    mg811Memoria.putBool("v3ok", false);
    Serial.printf("MG811: C1 %.1f ppm NDIR con GPIO35 %.2f mV\n", referencia, adcMv);
    return;
  }
  if (c2) {
    if (fabsf(adcMv - mg811V1) < 10.0f ||
        fabsf(referencia - mg811Ppm1) < 200.0f) {
      Serial.println("MG811: separacion insuficiente entre puntos; NO calibrado");
      return;
    }
    mg811V2 = adcMv;
    mg811Ppm2 = referencia;
    mg811TieneC2 = true;
    mg811ValidacionTercero = false;
    mg811ErrorValidacionPct = NAN;
    mg811Memoria.putFloat("v2", mg811V2);
    mg811Memoria.putFloat("p2", mg811Ppm2);
    mg811Memoria.putBool("c2", true);
    mg811Memoria.putBool("v3ok", false);
    Serial.printf("MG811: C2 %.1f ppm NDIR con GPIO35 %.2f mV\n", referencia, adcMv);
    Serial.println("MG811: modelo ppm disponible SOLO entre C1-C2; validar con tercer punto");
    return;
  }
  // Tercer punto independiente: no cambia la curva, verifica error.
  float estimacion = NAN;
  const float lo = min(mg811V1, mg811V2), hi = max(mg811V1, mg811V2);
  if (adcMv >= lo && adcMv <= hi) {
    const float f = (adcMv - mg811V1) / (mg811V2 - mg811V1);
    estimacion = expf(logf(mg811Ppm1) + f * (logf(mg811Ppm2) - logf(mg811Ppm1)));
  }
  if (!isfinite(estimacion)) {
    Serial.println("MG811: referencia 3 fuera del intervalo calibrado");
    return;
  }
  mg811ErrorValidacionPct = 100.0f * fabsf(estimacion - referencia) / referencia;
  mg811ValidacionTercero = mg811ErrorValidacionPct <= 15.0f;
  mg811Memoria.putBool("v3ok", mg811ValidacionTercero);
  mg811Memoria.putFloat("error3", mg811ErrorValidacionPct);
  Serial.printf("MG811: validacion NDIR=%.1f ppm, MG811=%.1f ppm, error=%.1f%%: %s\n",
                referencia, estimacion, mg811ErrorValidacionPct,
                mg811ValidacionTercero ? "APROBADA_PROVISIONAL" : "NO_APROBADA");
}

// Serial sin readStringUntil() para no bloquear mas de 750 ms los motores.
void revisarComandosCo2() {
  int caracteres = 0;
  while (Serial.available() && caracteres++ < 32) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (entradaSerialCo2.length()) procesarComandoCo2(entradaSerialCo2);
      entradaSerialCo2 = "";
    } else if (entradaSerialCo2.length() < 64) {
      entradaSerialCo2 += c;
    } else {
      entradaSerialCo2 = "";
    }
  }
}

String mg811Json() {
  String json;
  json.reserve(620);
  json += "{\"estado\":\"";
  json += mg811Estado();
  json += "\",\"gpio\":35";
  json += ",\"raw\":" + numeroOAsignarNull(mg811Raw, 1);
  json += ",\"adc_mv\":" + numeroOAsignarNull(mg811AdcMv, 2);
  json += ",\"aout_v\":" + numeroOAsignarNull(mg811AoutV, 4);
  json += ",\"co2_ppm\":" + numeroOAsignarNull(mg811Ppm, 1);
  json += ",\"calibrado\":";
  json += mg811Calibrado() ? "true" : "false";
  json += ",\"estable_10min\":";
  json += mg811Estable ? "true" : "false";
  json += ",\"deriva_10min_mv\":" + numeroOAsignarNull(mg811DerivaMv, 2);
  json += ",\"rango_10min_mv\":" + numeroOAsignarNull(mg811RangoMv, 2);
  json += ",\"alimentacion_v\":6.0";
  json += ",\"linea_base_adc_mv\":" + numeroOAsignarNull(mg811BaseAdcMv, 2);
  json += ",\"delta_aout_mv\":" + numeroOAsignarNull(mg811DeltaAoutMv, 2);
  json += ",\"evento_senal\":\"" + String(mg811Evento) + "\"";
  json += ",\"umbral_evento_aout_mv\":" + String(MG811_UMBRAL_CAMBIO_AOUT_MV, 1);
  json += ",\"listo_para_referencia\":";
  json += (mg811Estable && millis() >= MG811_PRECALENTAMIENTO_MS &&
           !mg811RevisarADC && !motoresActivos) ? "true" : "false";
  json += ",\"ppm_validado_tercer_punto\":";
  json += mg811ValidacionTercero ? "true" : "false";
  json += ",\"error_validacion_pct\":" + numeroOAsignarNull(mg811ErrorValidacionPct, 2);
  json += ",\"metodo_ppm\":\"interpolacion_logaritmica_dos_referencias_NDIR\"";
  json += "}";
  return json;
}

String movimientoActual() {
  int izq = pwmIzquierdoActual;
  int der = pwmDerechoActual;
  if (izq == 0 && der == 0) return "STOP";
  if (izq > 0 && der > 0) {
    if (izq == der) return "AVANZAR";
    return izq < der ? "IZQUIERDA" : "DERECHA";
  }
  if (izq < 0 && der < 0) {
    if (izq == der) return "RETROCEDER";
    return "GIRO_EN_REVERSA";
  }
  if (izq == 0 && der > 0) return "IZQUIERDA";
  if (der == 0 && izq > 0) return "DERECHA";
  return "GIRO_SOBRE_EJE";
}

String estadoJson(const char* comando) {
  String json = "{\"robot\":\"MeteoBot\",\"modo\":\"autonomo\",\"comando\":\"";
  json += comando;
  json += "\",\"izq\":" + String(pwmIzquierdoActual);
  json += ",\"der\":" + String(pwmDerechoActual);
  json += ",\"movimiento\":\"" + movimientoActual() + "\"";
  json += ",\"motores_activos\":";
  json += motoresActivos ? "true" : "false";
  json += "}";
  return json;
}

String sensoresJson() {
  String json;
  json.reserve(1600);
  String estadoGlobal = "OK";
  if (!shtConectado || !sharpListo || !bfsListo || !mg811Listo || sharpAdcAlto || bfsRevisarADC || mg811RevisarADC || !mg811Calibrado()) {
    estadoGlobal = "PARCIAL";
  }
  json += "{\"robot\":\"MeteoBot\",\"origen\":\"ESP32\",\"uptime_ms\":";
  json += String(millis());
  json += ",\"estado\":\"" + estadoGlobal + "\"";
  json += ",\"movimiento\":\"" + movimientoActual() + "\"";
  json += ",\"motores\":{\"izquierdo\":" + String(pwmIzquierdoActual);
  json += ",\"derecho\":" + String(pwmDerechoActual);
  json += ",\"maximo\":255,\"activos\":";
  json += motoresActivos ? "true" : "false";
  json += "}";
  json += ",\"sht3x\":{\"estado\":\"";
  json += shtConectado && isfinite(temperatura) ? "OK" : "SIN_DATOS";
  json += "\",\"temperatura\":" + numeroOAsignarNull(temperatura, 2);
  json += ",\"humedad\":" + numeroOAsignarNull(humedad, 2);
  json += "}";
  json += ",\"sharp\":{\"estado\":\"";
  json += !sharpListo ? "SIN_DATOS" : (sharpAdcAlto ? "REVISION_ADC" : "LECTURA");
  json += "\",\"raw\":" + numeroOAsignarNull(sharpRaw, 1);
  json += ",\"raw_min\":" + (sharpListo ? String(sharpMinRaw) : String("null"));
  json += ",\"raw_max\":" + (sharpListo ? String(sharpMaxRaw) : String("null"));
  json += ",\"adc_mv\":" + numeroOAsignarNull(sharpAdcMv, 1);
  json += ",\"vo_v\":" + numeroOAsignarNull(sharpVoV, 4);
  json += ",\"adc_alto\":";
  json += sharpAdcAlto ? "true" : "false";
  json += "}";
  json += ",\"bfs302\":{\"estado\":\"";
  json += !bfsListo ? "SIN_DATOS" : (bfsRevisarADC ? "REVISION_ADC" : "LECTURA");
  json += "\",\"raw\":" + numeroOAsignarNull(bfsRaw, 1);
  json += ",\"adc_mv\":" + numeroOAsignarNull(bfsAdcMv, 1);
  json += ",\"aout_v\":" + numeroOAsignarNull(bfsAoutV, 3);
  json += ",\"dout\":" + (bfsListo ? String(bfsDout) : String("null"));
  json += "},\"mg811\":" + mg811Json();
  json += "}";
  return json;
}

void configurarServidor() {
  server.on("/", HTTP_GET, []() { server.send(200, "application/json", estadoJson("ESTADO")); });
  server.on("/estado", HTTP_GET, []() { server.send(200, "application/json", estadoJson("ESTADO")); });
  server.on("/sensores", HTTP_GET, []() { server.send(200, "application/json", sensoresJson()); });
  server.on("/co2", HTTP_GET, []() { server.send(200, "application/json", mg811Json()); });
  server.on("/motores", HTTP_POST, []() {
    if (!server.hasArg("izq") || !server.hasArg("der")) {
      detener();
      server.send(400, "application/json", "{\"error\":\"Faltan parametros izq y der\",\"seguridad\":\"STOP\"}");
      return;
    }
    aplicarMotores(server.arg("izq").toInt(), server.arg("der").toInt());
    server.send(200, "application/json", estadoJson("MOTORES"));
  });
  server.on("/avanzar", HTTP_POST, []() {
    aplicarMotores(VELOCIDAD_AVANCE, VELOCIDAD_AVANCE);
    server.send(200, "application/json", estadoJson("AVANZAR"));
  });
  server.on("/izquierda", HTTP_POST, []() {
    aplicarMotores(VELOCIDAD_GIRO, VELOCIDAD_AVANCE);
    server.send(200, "application/json", estadoJson("IZQUIERDA"));
  });
  server.on("/derecha", HTTP_POST, []() {
    aplicarMotores(VELOCIDAD_AVANCE, VELOCIDAD_GIRO);
    server.send(200, "application/json", estadoJson("DERECHA"));
  });
  server.on("/retroceder", HTTP_POST, []() {
    aplicarMotores(-VELOCIDAD_AVANCE, -VELOCIDAD_AVANCE);
    server.send(200, "application/json", estadoJson("RETROCEDER"));
  });
  server.on("/stop", HTTP_POST, []() {
    detener();
    server.send(200, "application/json", estadoJson("STOP"));
  });
  server.onNotFound([]() { server.send(404, "application/json", "{\"error\":\"ruta no encontrada\"}"); });
  server.begin();
  servidorIniciado = true;
}

void revisarWiFi() {
  bool conectado = WiFi.status() == WL_CONNECTED;
  if (conectado && !wifiAnterior) {
    Serial.print("IP ESP32: ");
    Serial.println(WiFi.localIP());
    if (!servidorIniciado) configurarServidor();
  }
  if (!conectado) {
    if (motoresActivos) detener();
    if (millis() - ultimoIntentoWiFi > 10000) {
      ultimoIntentoWiFi = millis();
      WiFi.reconnect();
    }
  }
  wifiAnterior = conectado;
}

void setup() {
  Serial.begin(115200);
  delay(500);
  configurarMotores();
  detener();

  pinMode(SHARP_LED_PIN, OUTPUT);
  digitalWrite(SHARP_LED_PIN, HIGH);
  pinMode(SHARP_SENSOR_PIN, INPUT);
  pinMode(BFS_AOUT_PIN, INPUT);
  pinMode(BFS_DOUT_PIN, INPUT);
  pinMode(MG811_AOUT_PIN, INPUT);
  analogReadResolution(12);
  analogSetPinAttenuation(SHARP_SENSOR_PIN, ADC_11db);
  analogSetPinAttenuation(BFS_AOUT_PIN, ADC_11db);
  analogSetPinAttenuation(MG811_AOUT_PIN, ADC_2_5db);

  // Calibracion independiente para GPIO35: no reutilizar datos de GPIO34.
  mg811Memoria.begin("mg811_35", false);
  mg811TieneC1 = mg811Memoria.getBool("c1", false);
  mg811TieneC2 = mg811Memoria.getBool("c2", false);
  mg811V1 = mg811Memoria.getFloat("v1", 0);
  mg811V2 = mg811Memoria.getFloat("v2", 0);
  mg811Ppm1 = mg811Memoria.getFloat("p1", 0);
  mg811Ppm2 = mg811Memoria.getFloat("p2", 0);
  mg811ValidacionTercero = mg811Memoria.getBool("v3ok", false);
  mg811ErrorValidacionPct = mg811Memoria.getFloat("error3", NAN);

  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(100000);
  conectarSht();

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(ssid, password);
  ultimoIntentoWiFi = millis();
  Serial.println("SALUD AMBIENTAL METEOBOT V7.2 - MOTORES + SHT3x + SHARP + BFS302 + MG811 GPIO35");
  Serial.println("GET /estado, /sensores, /co2");
  Serial.println("MG811 comandos: HELP_CO2, BASE_CO2, RESET_BASE, C1 <ppm NDIR>, C2 <ppm NDIR>, VALIDAR_CO2 <ppm NDIR>, RESET_CO2");
  Serial.println("NO existe curva real en ppm hasta medir referencias NDIR. Eventos = cambios analogicos, no CO2 confirmado.");
  Serial.println("POST /motores?izq=...&der=..., /avanzar, /retroceder, /izquierda, /derecha, /stop");
  Serial.println("SDS011 se lee en Raspberry Pi; NO esta conectado al ESP32.");
}

void loop() {
  revisarWiFi();
  if (wifiAnterior && servidorIniciado) server.handleClient();
  if (motoresActivos && millis() - ultimaOrden > TIMEOUT_SEGURIDAD) {
    detener();
    Serial.println("WATCHDOG -> STOP");
  }
  leerSharp();
  leerSht();
  leerBfs();
  leerMg811();
  revisarComandosCo2();

  if (millis() - ultimaImpresion >= 2000) {
    ultimaImpresion = millis();
    Serial.println();
    Serial.println("============== METEOBOT ==============");
    Serial.printf("ESP32 WiFi: %s | IP: %s\n",
      WiFi.status() == WL_CONNECTED ? "OK" : "SIN CONEXION",
      WiFi.localIP().toString().c_str());
    Serial.printf("Movimiento: %s | PWM izq: %d | der: %d\n",
      movimientoActual().c_str(), pwmIzquierdoActual, pwmDerechoActual);
    Serial.printf("SHT3x: T=%.2f C, HR=%.2f %%\n", temperatura, humedad);
    Serial.printf("Sharp: Vo=%.4f V | RAW=%.1f | ADC alto=%s\n",
      sharpVoV, sharpRaw, sharpAdcAlto ? "SI" : "NO");
    Serial.printf("BFS-302: AOUT=%.3f V | RAW=%.1f | DOUT=%d | Revisar ADC=%s\n",
      bfsAoutV, bfsRaw, bfsDout, bfsRevisarADC ? "SI" : "NO");
    Serial.printf("MG811 CO2 (GPIO35): AOUT=%.4f V | ADC=%.2f mV | ppm=", mg811AoutV, mg811AdcMv);
    if (isfinite(mg811Ppm)) Serial.printf("%.1f", mg811Ppm);
    else Serial.print("SIN CALIBRAR / FUERA RANGO");
    Serial.printf(" | estado=%s | estable=%s | evento=%s",
                  mg811Estado(), mg811Estable ? "SI" : "NO", mg811Evento);
    if (isfinite(mg811DeltaAoutMv)) Serial.printf(" | deltaAOUT=%.1f mV", mg811DeltaAoutMv);
    Serial.println();
    Serial.println("======================================");
  }
}
