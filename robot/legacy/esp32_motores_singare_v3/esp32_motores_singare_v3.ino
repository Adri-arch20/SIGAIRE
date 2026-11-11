#include <WiFi.h>
#include <WebServer.h>

const char* ssid = "TU_SSID";
const char* password = "TU_PASSWORD";

WebServer server(80);

const int L_IN1_PIN = 4;
const int L_IN2_PIN = 17;
const int R_IN1_PIN = 27;
const int R_IN2_PIN = 13;

const int PWM_FREQ = 20000;
const int PWM_RES = 8;
const int VELOCIDAD_AVANCE = 180;

const unsigned long TIMEOUT_SEGURIDAD = 900;

unsigned long ultimaOrden = 0;
bool avanzando = false;

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

void avanzar() {
  motorIzquierdo(VELOCIDAD_AVANCE);
  motorDerecho(VELOCIDAD_AVANCE);

  avanzando = true;
  ultimaOrden = millis();
}

void detener() {
  motorIzquierdo(0);
  motorDerecho(0);

  avanzando = false;
}

void configurarServidor() {
  server.on("/", HTTP_GET, []() {
    server.send(
      200,
      "application/json",
      "{\"robot\":\"MeteoBot\",\"estado\":\"online\"}"
    );
  });

  server.on("/avanzar", HTTP_POST, []() {
    avanzar();

    server.send(
      200,
      "application/json",
      "{\"comando\":\"AVANZAR\",\"velocidad\":180}"
    );
  });

  server.on("/stop", HTTP_POST, []() {
    detener();

    server.send(
      200,
      "application/json",
      "{\"comando\":\"STOP\",\"velocidad\":0}"
    );
  });

  server.begin();
}

void setup() {
  Serial.begin(115200);
  delay(800);

  configurarMotores();
  detener();

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  Serial.println();
  Serial.println("METEOBOT - ESP32 SINGARE V3");
  Serial.print("Conectando");

  while (WiFi.status() != WL_CONNECTED) {
    Serial.print(".");
    delay(500);
  }

  Serial.println();
  Serial.print("IP ESP32: ");
  Serial.println(WiFi.localIP());

  configurarServidor();
}

void loop() {
  server.handleClient();

  if (
    avanzando &&
    millis() - ultimaOrden > TIMEOUT_SEGURIDAD
  ) {
    detener();
    Serial.println("WATCHDOG -> STOP");
  }
}
