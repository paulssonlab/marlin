#include <I2C.h>
#include <Adafruit_MCP4725.h>
// 300 for slow 2000 for fast
// 2000 fast for 3 mins to switch
// 300 slow for 2 mins to switch to MM



Adafruit_MCP4725 dac;

String state;
byte addresslist[] = {0x0E, 0x1E, 0x2E, 0x3E, 0x4E};//, 0x5E, 0x6E, 0x7E, 0x8E, 0x9E};
int titanxstates[] = {0,0,0,0,0};//,0,0,0,0,0};
int sizeoftitanxstates = 5;
int valvepin = 7;
int valvestate = 0;
int pumpstate = 0;

void setup() {
  Serial.begin(9600);
  while (!Serial) {
    ; // wait for serial port to connect. Needed for native USB port only
  }
  pinMode(valvepin, OUTPUT);
  digitalWrite(valvepin, LOW);
  valvestate = 0;
  
  dac.begin(0x62);
  dac.setVoltage(0, false);
  pumpstate = 0;
  
  I2c.begin();
  I2c.timeOut(1000);
  I2c.pullup(true);
}


void loop() {
  if (Serial.available() > 0){
    String state = "";
    state = Serial.readStringUntil('\r\n');
    Serial.println(state);
    if (state.length() > 0) {
  //    First, read the command number
        char cmd = state.charAt(0);
        if (cmd == '0' and state.length() == 1)
          {
            scanaddresses(titanxstates);
            printtitanxstates();
            Serial.println(valvestate);
            Serial.println(pumpstate);
          }
        if (cmd == '1' and state.length() == 3)
          {
            int addrint = state.substring(1,2).toInt();
            int newaddrint = state.substring(2,3).toInt();
            setaddress(addrint, newaddrint);
          }
        if (cmd == '2' and state.length() == 4)
          {
            int addrint = state.substring(1,2).toInt();
            int valveint = state.substring(2,4).toInt();
            setvalve(addrint, valveint);
          }
        
        if (cmd == '3' and state.length() == 5)
          {
            pumpstate = state.substring(1,5).toInt();
            dac.setVoltage(pumpstate, false);
          }
        if (cmd == '4' and state.length() == 2)
          {
            int valveval = state.substring(1,2).toInt();
            if (valveval == 0)
            {
              digitalWrite(valvepin, LOW);
              valvestate = valveval;
            }
            if (valveval == 1)
            {
              digitalWrite(valvepin, HIGH);
              valvestate = valveval;
            }
          }
    }
    else
    {
      while(Serial.available()) {
        Serial.read();
      }
    }
  }
}

void printtitanxstates(){
  Serial.print("[");
  for(int i = 0; i < sizeoftitanxstates-1; i++)
  {
    Serial.print(titanxstates[i]);
    Serial.print(",");
  }
  Serial.print(titanxstates[sizeoftitanxstates-1]);
  Serial.println("]");
}

void scanaddresses(int titanxstates[]){
  byte writeaddress, readaddress, incr, command, value, wchk, wack, rval, rchk;
  boolean getbyte = true;
  int addrint, readint;
  for(addrint = 0; addrint < sizeoftitanxstates; addrint++ ){
    writeaddress = addresslist[addrint];
    incr = 0x01;
    readaddress = writeaddress + incr;
    command = 0x53;
    value = 0x00;
    wchk = (writeaddress ^ command ^ value);

    I2c.start();
    wack = I2c.sendAddress(writeaddress);
        
    if (wack == 0) {
      I2c.sendByte(command);
      I2c.sendByte(value);
      I2c.sendByte(wchk);
      I2c.stop();
      
      I2c.start();
      I2c.sendAddress(readaddress);
      I2c.receiveByte(getbyte, &rval);
      I2c.receiveByte(getbyte, &rchk);
      I2c.stop();

//      Serial.print("Address: ");
//      String addrstring = String(addrint);
//      Serial.print(addrstring);
//      Serial.print(" | Valve State: ");
//      String valvestring = String(rval);
//      Serial.println(valvestring);
      titanxstates[addrint] = rval;

      I2c.start();
      wack = I2c.sendAddress(writeaddress);
      I2c.stop();
    }
    else {
      titanxstates[addrint] = 0;
      I2c.stop();
    }
  }
}


void setaddress(int addrint, int newaddrint){
  byte address, newaddress, command, chk;
  address = addresslist[addrint];
  newaddress = addresslist[newaddrint];
  command = 0x4E;
  chk = (address ^ command ^ newaddress);
  
  I2c.start();
  I2c.sendAddress(address);
  I2c.sendByte(command);
  I2c.sendByte(newaddress);
  I2c.sendByte(chk);
  I2c.stop();
}

void setvalve(int addrint, int valveint){
  byte address, command, chk, ack, valve;
  int iter;
  address = addresslist[addrint];
  valve = valveint;
  command = 0x50;
  chk = (address ^ command ^ valve);

  for(iter = 0; iter < 5; iter++) {
    I2c.start();
    ack = I2c.sendAddress(address);
    if (ack == 0) {
      I2c.sendByte(command);
      I2c.sendByte(valve);
      I2c.sendByte(chk);
      I2c.stop();
      break;
    }
    else {
      I2c.stop();
    }
  }
}
