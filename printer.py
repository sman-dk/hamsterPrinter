#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
from hamsterPrinter import hamsterPrinter
import argparse
import atexit
import time
import MySQLdb
from os.path import dirname, realpath, sep, pardir
basedir=dirname(realpath(__file__)) + sep

# Argument parsing

parser = argparse.ArgumentParser(description='Printer application for hamsterPrinter')
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
    mysqlConf[k] = cfg.get('mysql-printer', k)

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

# Load printer config
keys = ['dev', 'rotate', 'textSize', 'fontFile', 'printerWidth', 'printType']
printerConf = {}
for k in keys:
    printerConf[k] = cfg.get('printer', k)
if any([x in printerConf['rotate'] for x in ['true', 'True', 'yes', 'Yes', '180']]):
    printerConf['rotate'] = True
else:
    printerConf['rotate'] = False
printerConf['textSize'] = int(printerConf['textSize'])
printerConf['printerWidth'] = int(printerConf['printerWidth'])
optionalKeys = ['baudrate']
for k in optionalKeys:
    try:
        printerConf[k] = cfg.get('printer', k)
    except:
        pass

# Setup printer
printout = hamsterPrinter.printout(printerConf)

# Which feeds to print
printFeeds = [ i.lower() for i in cfg.get('printer', 'printFeeds').split()]
while True:
    if any(x in printFeeds for x in ['twitter','all']):
        printout.commonPrint(conn, 'Twitter')
    if any(x in printFeeds for x in ['facebook','all']):
        pass
    if any(x in printFeeds for x in ['weather','all']):
        printout.commonPrint(conn, 'WeatherCurrent')
        printout.commonPrint(conn, 'WeatherForecast')
    # Basic rate limiting. Also we do not want to query the database too often.
    time.sleep(2)