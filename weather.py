#!/usr/bin/python
# -*- coding: utf-8 -*-

from hamsterPrinter import hamsterPrinter
import argparse
import sys
import atexit
import time
import json
import requests
import MySQLdb
import schedule
from os.path import dirname, realpath, sep, pardir
basedir=dirname(realpath(__file__)) + sep

# Argument parsing

parser = argparse.ArgumentParser(description='Weather feeder for hamsterPrinter using the Apixu weather service')
parser.add_argument('-c', '--config', default='hamsterPrinter.cfg', type=str, 
                    help='Location of the configuration file')
args = parser.parse_args()

# Load config
hamster = hamsterPrinter.hamster()
cfg = hamster.readConfig(cfg=basedir + args.config)

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
weatherConf['apixu_api_url']='http://api.apixu.com/v1/'
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
        jsonObject = json.dumps(requests.get(weatherConf['apixu_api_url'] + 
            'current.json?key=' + weatherConf['apixuApiKey'] + 
            '&q=' + weatherConf['location'], timeout=30 ).json())
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
        jsonObject = json.dumps(requests.get(weatherConf['apixu_api_url'] + 
            'forecast.json?key=' + weatherConf['apixuApiKey'] + 
            '&q=' + weatherConf['location'] + '&days=' + weatherConf['ForecastDays'], timeout=30 ).json())
        dbWeather = conn.cursor()
        dbWeather.execute("""INSERT INTO printout (srcType, jdoc) VALUES (
            (SELECT id FROM srcType WHERE shortName = "WeatherForecast") , %s)""" , (jsonObject,))
        dbWeather.close()
    except Exception, e:
        print(e)
    else:
        print "Inserted a weather update of type WeatherCurrent into the database."

if "currentEnable" in weatherConf:
    if "currentEnforceUpdateInterval" in weatherConf:
        schedule.every(int(weatherConf["currentEnforceUpdateInterval"])).seconds.do(lambda: weatherCurrent(weatherConf))
    if "currentEnforceUpdateTime" in weatherConf:
        for t in weatherConf["currentEnforceUpdateTime"].split():
            schedule.every().day.at(str(t)).do(lambda: weatherCurrent(weatherConf))

if "ForecastEnable" in weatherConf:
    if "ForecastEnforceUpdateInterval" in weatherConf:
        schedule.every(int(weatherConf["ForecastEnforceUpdateInterval"])).seconds.do(lambda: weatherForecast(weatherConf))
    if "ForecastEnforceUpdateTime" in weatherConf:
        for t in weatherConf["ForecastEnforceUpdateTime"].split():
            schedule.every().day.at(str(t)).do(lambda: weatherForecast(weatherConf))

# Main loop
while True:
    schedule.run_pending()
    # The "pin it" feature..
    if "currentEnable" in weatherConf:
        if hamster.pinAgain("WeatherCurrent", conn, chuteLengthPx, cfg):
            weatherCurrent(weatherConf)
    if "ForecastEnable" in weatherConf:
        if hamster.pinAgain("WeatherForecast", conn, chuteLengthPx, cfg):
            weatherForecast(weatherConf)
        pass

    time.sleep(10)


