// Пример C — Музыкальный проект
#include <Arduino.h>

const uint8_t PIN_BUZZER = 10;
const uint8_t PIN_BUTTON = 2;

const int melody[] = {262, 294, 330, 349, 392};
const int N_NOTES = sizeof(melody) / sizeof(melody[0]);
const int NOTE_MS = 250;
const int PAUSE_MS = 50;

void playMelody() {
  for (int i = 0; i < N_NOTES; ++i) {
    tone(PIN_BUZZER, melody[i], NOTE_MS);
    delay(NOTE_MS + PAUSE_MS);
  }
  noTone(PIN_BUZZER);
}

void setup() {
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_BUTTON, INPUT_PULLUP);
}

void loop() {
  static bool prev = false;
  bool now = (digitalRead(PIN_BUTTON) == LOW);
  if (now && !prev) {
    playMelody();
  }
  prev = now;
  delay(10);
}
