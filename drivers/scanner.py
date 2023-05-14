from bluepy import btle
import struct
import itertools
import datetime
import logging

logger = logging.getLogger(__name__)


#Broadcastデータ取得用デリゲート
class SwitchbotScanDelegate(btle.DefaultDelegate):
    #コンストラクタ
    def __init__(self, config, on_new_data):
        btle.DefaultDelegate.__init__(self)
        self.config = config
        self.on_new_data = on_new_data
        self.reader_mapper = {
                "meters": {
                    "v0": self._decodeSensorData,
                },
                "plugs": {
                    "v0": self._decodePlugData,
                },
        }

    # スキャンハンドラー
    def handleDiscovery(self, dev, isNewDev, isNewData):
        if not isNewData and not isNewDev:
            return
        for device_type, mapper in self.reader_mapper.items():
            for mapper_version, decode_func in mapper.items():
                for alias, entry in self.config[device_type][mapper_version].items():
                    if dev.addr == entry["MacAddress"].lower():
                        raw_data_map = {desc: value for (adtype, desc, value) in dev.getScanData()}
                        logger.debug("Discovered %s addr=%s data=%s", alias, dev.addr, raw_data_map)
                        data = decode_func(raw_data_map)
                        if not data:
                            logger.debug("Failed to decode data for %s", alias)
                            continue
                        data.update({
                            "Datetime": datetime.datetime.now(),
                        })
                        self.on_new_data({
                            device_type: {
                                mapper_version: {
                                    alias: data
                                },
                            },
                        })

    # センサデータを取り出してdict形式に変換
    def _decodeSensorData(self, raw_data_map):
        if "16b Service Data" not in raw_data_map:
            return None
        if "Manufacturer" in raw_data_map and len(raw_data_map["16b Service Data"]) == 10: # Is outdoor meter
            data1 = bytes.fromhex(raw_data_map["Manufacturer"])
            data2 = bytes.fromhex(raw_data_map["16b Service Data"])
            batt = data2[4] & 0b01111111
            isTemperatureAboveFreezing = data1[11] & 0b10000000
            temp = ( data1[10] & 0b00001111 ) / 10 + (data1[11] & 0b01111111)
            if not isTemperatureAboveFreezing:
                temp = -temp
            humid = data1[12] & 0b01111111
            return {
                'Temperature': temp,
                'Humidity': humid,
                'BatteryVoltage': batt
            }
        elif len(raw_data_map["16b Service Data"]) == 16: # Is indoor meter plus
            #文字列からセンサデータ(4文字目以降)のみ取り出し、バイナリに変換
            valueBinary = bytes.fromhex(raw_data_map["16b Service Data"][4:])
            #バイナリ形式のセンサデータを数値に変換
            batt = valueBinary[2] & 0b01111111
            isTemperatureAboveFreezing = valueBinary[4] & 0b10000000
            temp = ( valueBinary[3] & 0b00001111 ) / 10 + ( valueBinary[4] & 0b01111111 )
            if not isTemperatureAboveFreezing:
                temp = -temp
            humid = valueBinary[5] & 0b01111111
            return {
                'Temperature': temp,
                'Humidity': humid,
                'BatteryVoltage': batt
            }
        return None

    def _decodePlugData(self, raw_data_map):
        valueStr = raw_data_map["Manufacturer"]
        if (len(valueStr) == 28):
            power = (int(valueStr[24:28].encode('utf-8'), 16)) / 10.0
            sw = bool(int(valueStr[18].encode('utf-8'), 16 ) >> 3)
            return {
                "Power": power,
                "Switch": sw,
            }
        return None

