# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license.

import iotc
from iotc import IOTConnectType, IOTLogLevel
from random import randint

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

iotc.connect()

while iotc.isConnected():
  iotc.doNext() # do the async work needed to be done for MQTT
  if gCanSend == True:
    if gCounter % 20 == 0:
      gCounter = 0
      print("Sending telemetry..")
      iotc.sendTelemetry("{ \
\"temp\": " + str(randint(20, 45)) + ", \
\"accelerometerX\": " + str(randint(2, 15)) + ", \
\"accelerometerY\": " + str(randint(3, 9)) + ", \
\"accelerometerZ\": " + str(randint(1, 4)) + "}")

    gCounter += 1
