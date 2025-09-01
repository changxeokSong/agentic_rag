#include <Wire.h>
#include <TCA9548A.h> // I2C 멀티플렉서 라이브러리

#ifdef ARDUINO_SAMD_VARIANT_COMPLIANCE
#define SERIAL SerialUSB
#else
#define SERIAL Serial
#endif

// --- I2C 멀티플렉서 객체 생성 ---
TCA9548A<TwoWire> TCA;

// --- 핀 설정 ---
const int PUMP_PIN1 = 13;
const int PUMP_PIN2 = 6;

// --- 센서 I2C 주소 및 임계값 ---
#define ATTINY1_HIGH_ADDR   0x78
#define ATTINY2_LOW_ADDR    0x77
#define THRESHOLD           100

// --- 측정할 센서 채널 목록 ---
// 여기에 실제로 사용하는 멀티플렉서의 채널 번호를 입력하세요.
int sensorChannels[] = {1, 2}; // 예시: 0, 1, 2번 채널의 센서를 모두 읽음
const int numSensors = sizeof(sensorChannels) / sizeof(sensorChannels[0]);


void setup() {
  SERIAL.begin(115200);
  while(!Serial);
  delay(1000);

  Wire.begin();
  TCA.begin(Wire); // I2C 멀티플렉서 초기화

  pinMode(PUMP_PIN1, OUTPUT);
  pinMode(PUMP_PIN2, OUTPUT);
  
  digitalWrite(PUMP_PIN1, LOW);
  digitalWrite(PUMP_PIN2, LOW);
  
  SERIAL.println("Arduino is ready. Commands: read_water_level, read_water_level_X, PUMP_...");
}

void loop() {
  if (SERIAL.available() > 0) {
    String command = SERIAL.readStringUntil('\n');
    command.trim();

    // "read_water_level" 명령: 정의된 모든 센서 값을 순차적으로 읽음
    if (command == "read_water_level") {
      SERIAL.println("--- Reading all connected sensors ---");
      for (int i = 0; i < numSensors; i++) {
        readAndSendWaterLevel(sensorChannels[i]);
        delay(100); // 센서 간 안정적인 읽기를 위한 짧은 딜레이
      }
      SERIAL.println("-----------------------------------");
    }
    // "read_water_level_X" 명령: 특정 채널의 센서 값만 읽음
    else if (command.startsWith("read_water_level_")) {
      int channel = command.substring(command.lastIndexOf('_') + 1).toInt();
      readAndSendWaterLevel(channel);
    }
    else if (command.startsWith("PUMP1_ON")) {
      controlPump(PUMP_PIN1, HIGH, command);
    }
    else if (command == "PUMP1_OFF") {
      digitalWrite(PUMP_PIN1, LOW);
      SERIAL.println("ACK: Pump 1 is now OFF.");
    }
    else if (command.startsWith("PUMP2_ON")) {
      controlPump(PUMP_PIN2, HIGH, command);
    }
    else if (command == "PUMP2_OFF") {
      digitalWrite(PUMP_PIN2, LOW);
      SERIAL.println("ACK: Pump 2 is now OFF.");
    }
    else if (command == "PUMP_STATUS") {
      sendStatus();
    }
    // 연결 테스트를 위한 PING 명령 처리
    else if (command == "PING") {
      SERIAL.println("PONG");
    }
  }
}

// 펌프 제어 함수 (수정 없음)
void controlPump(int pin, int state, String command) {
  int duration = 0;
  int lastUnderscore = command.lastIndexOf('_');
  if (lastUnderscore != -1 && lastUnderscore < command.length() - 1) {
    String durationStr = command.substring(lastUnderscore + 1);
    duration = durationStr.toInt();
  }

  digitalWrite(pin, state);
  SERIAL.print("ACK: Pump ");
  SERIAL.print((pin == PUMP_PIN1) ? 1 : 2);
  SERIAL.println(" is now ON.");

  if (duration > 0) {
    delay(duration * 1000);
    digitalWrite(pin, LOW);
    SERIAL.print("ACK: Pump ");
    SERIAL.print((pin == PUMP_PIN1) ? 1 : 2);
    SERIAL.println(" turned OFF after duration.");
  }
}

// 지정된 채널의 센서 값을 읽고 시리얼로 전송하는 함수 (수정 없음)
void readAndSendWaterLevel(int channel) {
  TCA.openChannel(channel);

  unsigned char low_data[8] = {0};
  unsigned char high_data[12] = {0};

  Wire.requestFrom(ATTINY2_LOW_ADDR, 8);
  if (Wire.available() < 8) {
    SERIAL.print("Error: Failed to read from sensor on Channel ");
    SERIAL.println(channel);
    while(Wire.available()) Wire.read();
    TCA.closeChannel(channel);
    return;
  }
  for (int i = 0; i < 8; i++) {
    low_data[i] = Wire.read();
  }

  Wire.requestFrom(ATTINY1_HIGH_ADDR, 12);
  if (Wire.available() < 12) {
    SERIAL.print("Error: Failed to read from sensor on Channel ");
    SERIAL.println(channel);
    while(Wire.available()) Wire.read();
    TCA.closeChannel(channel);
    return;
  }
  for (int i = 0; i < 12; i++) {
    high_data[i] = Wire.read();
  }
  
  TCA.closeChannel(channel);

  uint32_t touch_val = 0;
  uint8_t trig_section = 0;
  for (int i = 0; i < 8; i++) {
    if (low_data[i] > THRESHOLD) {
      touch_val |= (uint32_t)1 << i;
    }
  }
  for (int i = 0; i < 12; i++) {
    if (high_data[i] > THRESHOLD) {
      touch_val |= (uint32_t)1 << (8 + i);
    }
  }
  while (touch_val & 0x01) {
    trig_section++;
    touch_val >>= 1;
  }
  int waterLevelPercent = trig_section * 5;

  SERIAL.print("Channel[");
  SERIAL.print(channel);
  SERIAL.print("] water level = ");
  SERIAL.print(waterLevelPercent);
  SERIAL.println("%");
}

// 펌프 상태 출력 함수 (수정 없음)
void sendStatus() {
  SERIAL.print("PUMP1_STATUS:");
  SERIAL.print(digitalRead(PUMP_PIN1) == HIGH ? "ON" : "OFF");
  SERIAL.print(",");
  SERIAL.print("PUMP2_STATUS:");
  SERIAL.println(digitalRead(PUMP_PIN2) == HIGH ? "ON" : "OFF");
}