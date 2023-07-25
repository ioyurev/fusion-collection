// this example is public domain. enjoy!
// https://learn.adafruit.com/thermocouple/

#include "max6675.h"

int thermoDO1 = 12;
int thermoCS1 = 9;
int thermoCLK1 = 13;

int thermoDO2 = 12;
int thermoCS2 = 10;
int thermoCLK2 = 13;

unsigned long start_time;
unsigned long time;
float t1;
float t2;

MAX6675 thermocouple1(thermoCLK1, thermoCS1, thermoDO1);
MAX6675 thermocouple2(thermoCLK2, thermoCS2, thermoDO2);

void setup() {
  Serial.begin(9600);

  Serial.println("MAX6675 test");
  // wait for MAX chip to stabilize
  delay(500);
  start_time = millis();
}

void loop() {
  // basic readout test, just print the current temp
  
  //  Serial.print("C = "); 
   t1 = thermocouple1.readCelsius();
   t2 = thermocouple2.readCelsius();
   time = millis() - start_time;
   Serial.print(time);
   Serial.print(",");
   Serial.print(t1);
   Serial.print(",");
   Serial.print(t2);
 
   // For the MAX6675 to update, you must delay AT LEAST 250ms between reads!
   delay(250);
}