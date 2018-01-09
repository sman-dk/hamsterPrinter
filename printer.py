#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '../pyPOSprinter')
from hamsterPrinter import hamsterPrinter
from pyqrnative import PyQRNative
from POSprinter import POSprinter
import argparse
import atexit
import time
import json
import MySQLdb

# Argument parsing

parser = argparse.ArgumentParser(description='Printer application for hamsterPrinter')
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
keys = ['dev', 'rotate', 'textSize', 'fontFile']
printerConf = {}
for k in keys:
    printerConf[k] = cfg.get('printer', k)
print printerConf['rotate']
if any([x in printerConf['rotate'] for x in ['true', 'True', 'yes', 'Yes', '180']]):
    printerConf['rotate'] = True
else:
    printerConf['rotate'] = False
print printerConf['rotate']
printerConf['textSize'] = int(printerConf['textSize'])

# Setup printer
posprinter = POSprinter.POSprinter(port=printerConf['dev'])
printout = hamsterPrinter.printout(posprinter)
currentpxWidth = 2 * posprinter.pxWidth

# Which feeds to print
printFeeds = [ i for i in cfg.get('mysql-printer', 'printFeeds').split()]
while True:
    if any(x in printFeeds for x in ['Twitter','twitter','all']):
        try:
            dbPrinter = conn.cursor()
            dbPrinter.execute("""SELECT id, jdoc FROM printout WHERE printed = 0 ORDER BY id ASC LIMIT 1""")
            tweet = dbPrinter.fetchone()
            # if there is unprinted tweets waiting for us
            if tweet is not None:
                tweetData = json.loads(tweet[1])
                printData = printout.twitter(tweetData, currentpxWidth, printerConf)
                # Hmm. one could argue that if printing something fails, 
                # then the message should not be marked as printed in the db..
                dbPrinter.execute("""UPDATE printout SET height = %s, 
                    printed = 1, printedImg = _binary %s, printedImgRotated = %s, 
                    printedImgMimeType = %s WHERE id=%s""", (str(printData[0]),
                    printData[1], str(printData[2]),
                    printData[3], str(tweet[0])))
            dbPrinter.close()
        except Exception, e:
            print(e)
            try:
                print("The id for the failed message in the printout table: %i" % tweet[0])
            except:
                pass
        else:
            if tweet is not None:
                print("Printed a twitter message from %s to the printer".encode('utf-8') % tweetData['screen_name'])
    elif any(x in printFeeds for x in ['Facebook','facebook','all']):
        pass
    # Basic rate limiting. Also we do not want to query the database too often.
    time.sleep(2)