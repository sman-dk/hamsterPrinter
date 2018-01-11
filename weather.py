#!/usr/bin/python
# -*- coding: utf-8 -*-

from hamsterPrinter import hamsterPrinter
import argparse
import sys
import atexit
import time
import json
import MySQLdb
import schedule
from WeatherAPIXU import Weather_APIXU

# Argument parsing

parser = argparse.ArgumentParser(description='Weather feeder for hamsterPrinter using the Apixu weather service')
parser.add_argument('-c', '--config', default='hamsterPrinter.cfg', type=str, 
                    help='Location of the configuration file')
args = parser.parse_args()

# Load config
hamster = hamsterPrinter.hamster()
cfg = hamster.readConfig(cfg=args.config)

# Connect to mysql


keys = ['host', 'user', 'passphrase', 'dbName']
mysqlConf = {}
for k in keys:
    mysqlConf[k] = cfg.get('mysql-feeder', k)

conn = MySQLdb.connect(
    host = mysqlConf['host'], 
    user = mysqlConf['user'],
    passwd = mysqlConf['passphrase'],
    db = mysqlConf['dbName'],
    charset='utf8',
    use_unicode=True)
conn.autocommit(True)

# Close the mysql connection when exiting the program
def exit_handler():
    conn.close()
atexit.register(exit_handler)


# Load weather config
keys = ['apixuApiKey', 'location', 'chuteLength']
weatherConf = {}
for k in keys:
    weatherConf[k] = cfg.get('weather', k)
# optional parameters
keys = ['currentEnable', 'currentEnforceUpdateInterval', 
    'currentEnforceUpdateTime', 'ForecastEnable',
    'ForecastEnforceUpdateInterval', 'ForecastEnforceUpdateTime',
    'ForecastDays']
for k in keys:
    try:
        weatherConf[k] = cfg.get('weather', k)
    except:
        pass
# Calculate chutePx
chuteLengthPx = int(int(weatherConf['chuteLength']) / 2.54 * int(cfg.get('printer', 'verticalDpi')))

def weatherCurrent(weatherConf):
    try:
        w = Weather_APIXU(weatherConf['apixuApiKey'])
        jsonObject = json.dumps(w.weather_current(query=weatherConf['location']))
        dbWeather = conn.cursor()
        dbWeather.execute("""INSERT INTO printout (srcType, jdoc) VALUES (
            (SELECT id FROM srcType WHERE shortName = "WeatherCurrent") , %s)""" , (jsonObject,))
        dbWeather.close()
    except Exception, e:
        print(e)
    else:
        print "Inserted a weather update of type WeatherCurrent into the database."


def weatherForecast(weatherConf):
    try:
        w = Weather_APIXU(weatherConf['apixuApiKey'])
        jsonObject = json.dumps(w.weather_forecast(query=weatherConf['location'], days=weatherConf['ForecastDays']))
        dbWeather = conn.cursor()
        dbWeather.execute("""INSERT INTO printout (srcType, jdoc) VALUES (
            (SELECT id FROM srcType WHERE shortName = "WeatherForecast") , %s)""" , (jsonObject,))
        dbWeather.close()
    except Exception, e:
        print(e)
    else:
        print "Inserted a weather update of type WeatherForecast into the database."

def weatherStuffUnfinished():
    try:
        dbWeather = conn.cursor()
        jsonObject = json.dumps({
            "name": "hest",
            "screen_name": "hest",
            "created_at": "hest",
            "timestamp_ms": "hest",
            "url": "hest",
            "text": "hest",
            "hashtags": "hest",
            "is_quote_status": "hest",
            "retweet": "hest",
            "urlPics": "hest"})
        dbWeather.execute("""INSERT INTO printout (srcType, jdoc) VALUES (
            (SELECT id FROM srcType WHERE shortName = "WeatherForecast") , %s)""" , (jsonObject,))
        dbWeather.close()
    except Exception, e:
        print(e)


if "currentEnable" in weatherConf:
    if "currentEnforceUpdateInterval" in weatherConf:
        schedule.every(int(weatherConf["currentEnforceUpdateInterval"])).seconds.do(lambda: weatherCurrent(weatherConf))
    if "currentEnforceUpdateTime" in weatherConf:
        for t in weatherConf["currentEnforceUpdateTime"].split():
            schedule.every().day.at(t).do(lambda: weatherCurrent(weatherConf))

#if "ForecastEnable" in weatherConf:
#    if "ForecastEnforceUpdateInterval" in weatherConf:
#        schedule.every(int(weatherConf["ForecastEnforceUpdateInterval"])).seconds.do(lambda: weatherForecast(weatherConf))
#    if "ForecastEnforceUpdateTime" in weatherConf:
#        for t in weatherConf["ForecastEnforceUpdateTime"].split():
#            schedule.every().day.at(t).do(lambda: weatherForecast(weatherConf))

# Main loop
while True:
    schedule.run_pending()
    # The "pin it" feature..
    if "currentEnable" in weatherConf:
        if hamster.pinAgain("WeatherCurrent", conn, chuteLengthPx, cfg):
            weatherCurrent(weatherConf)
    if "ForecastEnable" in weatherConf:
        #if hamster.pinAgain("WeatherForecast", conn, chuteLengthPx, cfg):
            #weatherForecast(weatherConf)
        pass

    time.sleep(10)


