// Пример B — Антистолкновение
#include <Arduino.h>

void motorSetSpeed(uint8_t port, int speed);

const uint8_t PIN_TRIG = 7;
const uint8_t PIN_ECHO = 8;
const int FWD_PWM = 140;
const int TURN_MS = 350;
const int STOP_MS = 150;
const float THRESHOLD_CM = 15.0f;

float readDistanceCm() {
  long duration;
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);
  duration = pulseIn(PIN_ECHO, HIGH, 30000);
  if (duration <= 0) return 9999.0f;
  return duration * 0.0343f / 2.0f;
}

void setup() {
  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
}

void loop() {
  float d = readDistanceCm();
  if (d < THRESHOLD_CM) {
    motorSetSpeed(1, 0);
    motorSetSpeed(2, 0);
    delay(STOP_MS);
    motorSetSpeed(1, -FWD_PWM);
    motorSetSpeed(2, FWD_PWM);
    delay(TURN_MS);
    motorSetSpeed(1, FWD_PWM);
    motorSetSpeed(2, FWD_PWM);
  } else {
    motorSetSpeed(1, FWD_PWM);
    motorSetSpeed(2, FWD_PWM);
  }
  delay(20);
}
