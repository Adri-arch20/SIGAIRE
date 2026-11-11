#include <WiFi.h>
#include <WebServer.h>
#include <Wire.h>
#include <Adafruit_SHT31.h>
#include <math.h>

// SALUD AMBIENTAL METEOBOT V7 - ESP32: motores + telemetria + SHT3x + Sharp + BFS-302
// Arduino IDE: core "esp32 by Espressif" 3.x; Adafruit SHT31 Library.
// IMPORTANTE: las salidas analogicas/digitales hacia ESP32 requieren <=3.3 V.
const char* ssid = "I.I";
const char* password = "CAMBIA_AQUI_TU_CONTRASENA";
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
  json.reserve(1000);
  String estadoGlobal = "OK";
  if (!shtConectado || !sharpListo || !bfsListo || sharpAdcAlto || bfsRevisarADC) {
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
  json += "}}";
  return json;
}

void configurarServidor() {
  server.on("/", HTTP_GET, []() { server.send(200, "application/json", estadoJson("ESTADO")); });
  server.on("/estado", HTTP_GET, []() { server.send(200, "application/json", estadoJson("ESTADO")); });
  server.on("/sensores", HTTP_GET, []() { server.send(200, "application/json", sensoresJson()); });
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
  analogReadResolution(12);
  analogSetPinAttenuation(SHARP_SENSOR_PIN, ADC_11db);
  analogSetPinAttenuation(BFS_AOUT_PIN, ADC_11db);

  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(100000);
  conectarSht();

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(ssid, password);
  ultimoIntentoWiFi = millis();
  Serial.println("METEOBOT ESP32 V5.2 - MOTORES + SHT3x + SHARP + BFS302");
  Serial.println("GET /estado, /sensores");
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
    Serial.println("======================================");
  }
}
