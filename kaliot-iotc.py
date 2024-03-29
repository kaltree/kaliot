# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license.

import iotc
from iotc import IOTConnectType, IOTLogLevel
from random import randint
import time

# BME280 - Temp, Pressure, Humidity - Headers
import smbus
from ctypes import c_short
from ctypes import c_byte
from ctypes import c_ubyte

### TCS34715 - Light Quality - Headers
import Adafruit_TCS34725
import Adafruit_GPIO



### BME280 - Temp, Pressure, Humidity

DEVICE = 0x77 # Default device I2C address


bus = smbus.SMBus(1) # Rev 2 Pi, Pi 2 & Pi 3 uses bus 1

def getShort(data, index):
  # return two bytes from data as a signed 16-bit value
  return c_short((data[index+1] << 8) + data[index]).value

def getUShort(data, index):
  # return two bytes from data as an unsigned 16-bit value
  return (data[index+1] << 8) + data[index]

def getChar(data,index):
  # return one byte from data as a signed char
  result = data[index]
  if result > 127:
    result -= 256
  return result

def getUChar(data,index):
  # return one byte from data as an unsigned char
  result =  data[index] & 0xFF
  return result

## Get TCS Data
def readTCSAll():
  avgr = 0
  avgg = 0
  avgb = 0
  avgc = 0
  count = 0
  while (count < 130):
    tcs = Adafruit_TCS34725.TCS34725()
    r, g, b, c = tcs.get_raw_data()
    avgr = avgr + r
    avgg = avgg + g
    avgb = avgb + b
    avgc = avgc + c
    count = count + 1
    tcs.disable()
  avgr = avgr/130
  avgg = avgg/130
  avgb = avgb/130
  avgc = avgc/130
  r = float(avgr)
  g = float(avgg)
  b = float(avgb)
  c = float(avgc)
  lux = float(Adafruit_TCS34725.calculate_lux(r, g, b))
  color_temp = Adafruit_TCS34725.calculate_color_temperature(r, g, b)
  if color_temp is None:
    color_temp = 0
  color_temp = float(color_temp)
  return r,g,b,c,lux,color_temp

def readBME280ID(addr=DEVICE):
  # Chip ID Register Address
  REG_ID     = 0xD0
  (chip_id, chip_version) = bus.read_i2c_block_data(addr, REG_ID, 2)
  return (chip_id, chip_version)

def readBME280All(addr=DEVICE):
  # Register Addresses
  REG_DATA = 0xF7
  REG_CONTROL = 0xF4
  REG_CONFIG  = 0xF5

  REG_CONTROL_HUM = 0xF2
  REG_HUM_MSB = 0xFD
  REG_HUM_LSB = 0xFE

  # Oversample setting - page 27
  OVERSAMPLE_TEMP = 2
  OVERSAMPLE_PRES = 2
  MODE = 1

  # Oversample setting for humidity register - page 26
  OVERSAMPLE_HUM = 2
  bus.write_byte_data(addr, REG_CONTROL_HUM, OVERSAMPLE_HUM)

  control = OVERSAMPLE_TEMP<<5 | OVERSAMPLE_PRES<<2 | MODE
  bus.write_byte_data(addr, REG_CONTROL, control)

  # Read blocks of calibration data from EEPROM
  # See Page 22 data sheet
  cal1 = bus.read_i2c_block_data(addr, 0x88, 24)
  cal2 = bus.read_i2c_block_data(addr, 0xA1, 1)
  cal3 = bus.read_i2c_block_data(addr, 0xE1, 7)

  # Convert byte data to word values
  dig_T1 = getUShort(cal1, 0)
  dig_T2 = getShort(cal1, 2)
  dig_T3 = getShort(cal1, 4)

  dig_P1 = getUShort(cal1, 6)
  dig_P2 = getShort(cal1, 8)
  dig_P3 = getShort(cal1, 10)
  dig_P4 = getShort(cal1, 12)
  dig_P5 = getShort(cal1, 14)
  dig_P6 = getShort(cal1, 16)
  dig_P7 = getShort(cal1, 18)
  dig_P8 = getShort(cal1, 20)
  dig_P9 = getShort(cal1, 22)

  dig_H1 = getUChar(cal2, 0)
  dig_H2 = getShort(cal3, 0)
  dig_H3 = getUChar(cal3, 2)

  dig_H4 = getChar(cal3, 3)
  dig_H4 = (dig_H4 << 24) >> 20
  dig_H4 = dig_H4 | (getChar(cal3, 4) & 0x0F)

  dig_H5 = getChar(cal3, 5)
  dig_H5 = (dig_H5 << 24) >> 20
  dig_H5 = dig_H5 | (getUChar(cal3, 4) >> 4 & 0x0F)

  dig_H6 = getChar(cal3, 6)

  # Wait in ms (Datasheet Appendix B: Measurement time and current calculation)
  wait_time = 1.25 + (2.3 * OVERSAMPLE_TEMP) + ((2.3 * OVERSAMPLE_PRES) + 0.575) + ((2.3 * OVERSAMPLE_HUM)+0.575)
  time.sleep(wait_time/1000)  # Wait the required time

  # Read temperature/pressure/humidity
  data = bus.read_i2c_block_data(addr, REG_DATA, 8)
  pres_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
  temp_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
  hum_raw = (data[6] << 8) | data[7]

  #Refine temperature
  var1 = ((((temp_raw>>3)-(dig_T1<<1)))*(dig_T2)) >> 11
  var2 = (((((temp_raw>>4) - (dig_T1)) * ((temp_raw>>4) - (dig_T1))) >> 12) * (dig_T3)) >> 14
  t_fine = var1+var2
  temperature = float(((t_fine * 5) + 128) >> 8);
  temperatureF = (temperature * 9 / 5) + 32

  # Refine pressure and adjust for temperature
  var1 = t_fine / 2.0 - 64000.0
  var2 = var1 * var1 * dig_P6 / 32768.0
  var2 = var2 + var1 * dig_P5 * 2.0
  var2 = var2 / 4.0 + dig_P4 * 65536.0
  var1 = (dig_P3 * var1 * var1 / 524288.0 + dig_P2 * var1) / 524288.0
  var1 = (1.0 + var1 / 32768.0) * dig_P1
  if var1 == 0:
    pressure=0
  else:
    pressure = 1048576.0 - pres_raw
    pressure = ((pressure - var2 / 4096.0) * 6250.0) / var1
    var1 = dig_P9 * pressure * pressure / 2147483648.0
    var2 = pressure * dig_P8 / 32768.0
    pressure = pressure + (var1 + var2 + dig_P7) / 16.0

  # Refine humidity
  humidity = t_fine - 76800.0
  humidity = (hum_raw - (dig_H4 * 64.0 + dig_H5 / 16384.0 * humidity)) * (dig_H2 / 65536.0 * (1.0 + dig_H6 / 67108864.0 * humidity * (1.0 + dig_H3 / 67108864.0 * humidity)))
  humidity = humidity * (1.0 - dig_H1 * humidity / 524288.0)
  if humidity > 100:
    humidity = 100
  elif humidity < 0:
    humidity = 0

  return temperatureF/100.0,pressure/100.0,humidity

## End BME

deviceId = "17f83c9b-e31c-4e11-8b9c-1b89ee99e714"
scopeId = "0ne00062CC3"
deviceKey = "V4sxmvey5dA5PBNqtCatp5uUZn/JwppsfIfZXdusocc="

iotc = iotc.Device(scopeId, deviceKey, deviceId, IOTConnectType.IOTC_CONNECT_SYMM_KEY)
iotc.setLogLevel(IOTLogLevel.IOTC_LOGGING_API_ONLY)

gCanSend = False
gCounter = 0

def onconnect(info):
  global gCanSend
  print("- [onconnect] => status:" + str(info.getStatusCode()))
  if info.getStatusCode() == 0:
     if iotc.isConnected():
       gCanSend = True

def onmessagesent(info):
  print("\t- [onmessagesent] => " + str(info.getPayload()))

def oncommand(info):
  print("- [oncommand] => " + info.getTag() + " => " + str(info.getPayload()))

def onsettingsupdated(info):
  print("- [onsettingsupdated] => " + info.getTag() + " => " + info.getPayload())

iotc.on("ConnectionStatus", onconnect)
iotc.on("MessageSent", onmessagesent)
iotc.on("Command", oncommand)
iotc.on("SettingsUpdated", onsettingsupdated)

# Start by Connecting then Sending
iotc.connect()
(airtemp,airpressure,airhumidity) = readBME280All(addr=DEVICE)
(r,g,b,c,lux,color_temp) = readTCSAll()
iotc.sendTelemetry("{ \
\"airtemperature\": " + str(airtemp) + ", \
\"airpressure\": " + str(airpressure) + ", \
\"airhumidity\": " + str(airhumidity) + ", \
\"lux\": " + str(lux) + ", \
\"colortemp\": " + str(color_temp) + ", \
\"green\": " + str(g) + ", \
\"blue\": " + str(b) + ", \
\"clear\": " + str(c) + ", \
\"red\": " + str(r) + "}")
starttime = time.time()
while iotc.isConnected():
  time.sleep(5)
  iotc.doNext() # do the async work needed to be done for MQTT
  elapsedtime = time.time() - starttime
  if elapsedtime > 66:
   print("Sending telemetry..")
   ## Collect Telemetry Data
   (airtemp,airpressure,airhumidity) = readBME280All(addr=DEVICE)
   (r,g,b,c,lux,color_temp) = readTCSAll()
   elapsedtime = 0
   starttime = time.time()
   iotc.sendTelemetry("{ \
\"airtemperature\": " + str(airtemp) + ", \
\"airpressure\": " + str(airpressure) + ", \
\"airhumidity\": " + str(airhumidity) + ", \
\"lux\": " + str(lux) + ", \
\"colortemp\": " + str(color_temp) + ", \
\"green\": " + str(g) + ", \
\"blue\": " + str(b) + ", \
\"clear\": " + str(c) + ", \
\"red\": " + str(r) + "}")
