// Пример A — Робот, следующий по линии
#include <Arduino.h>

const uint8_t PIN_LINE_LEFT  = A0;
const uint8_t PIN_LINE_RIGHT = A1;
const int BASE_SPEED = 120;
const float K = 0.15f;
const int MAX_CORR = 60;

void motorSetSpeed(uint8_t port, int speed);

void setup() {
  pinMode(PIN_LINE_LEFT, INPUT);
  pinMode(PIN_LINE_RIGHT, INPUT);
}

void loop() {
  int left = analogRead(PIN_LINE_LEFT);
  int right = analogRead(PIN_LINE_RIGHT);
  int err = (left - right);
  int corr = (int)(K * err);
  if (corr > MAX_CORR) corr = MAX_CORR;
  if (corr < -MAX_CORR) corr = -MAX_CORR;
  int vL = BASE_SPEED - corr;
  int vR = BASE_SPEED + corr;
  if (vL > 255) vL = 255;
  if (vL < -255) vL = -255;
  if (vR > 255) vR = 255;
  if (vR < -255) vR = -255;
  motorSetSpeed(1, vL);
  motorSetSpeed(2, vR);
}
