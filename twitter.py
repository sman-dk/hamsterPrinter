#!/usr/bin/python
# -*- coding: utf-8 -*-
# Ideas:
# Add support for following one or more users on Twitter 
#     (see https://github.com/tweepy/examples/blob/master/streamwatcher.py for an example)
# Possibility to tate limit (e.g. max X status/5 minutes) (maybe have a default)
# Possibility to block users (by id or name)

from hamsterPrinter import hamsterPrinter
import argparse
import sys
import tweepy
import atexit
import time
import json
import MySQLdb

# Argument parsing

parser = argparse.ArgumentParser(description='Twitter feeder for hamsterPrinter')
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

# Load twitter config
keys = ['consumerKey', 'consumerSecret', 'accessTokenKey', 'accessTokenSecret', 'filter']
twitterConf = {}
for k in keys:
    twitterConf[k] = cfg.get('twitter', k)

# Twitter streaming stuff
class StreamWatcherListener(tweepy.StreamListener):
    # Run when a Twitter status matches the filter
    def on_status(self, status):
        try:
            hasPics = False
            dbTwit = conn.cursor()
            if 'extended_entities' in dir(status):
                hasPics = True
                urlPics = [ media['media_url'] for media in status.extended_entities['media']]
            else:
                urlPics = [] 
            twitText = status.text 
            
            jsonObject = json.dumps({
                "name": status.author.name,
                "screen_name": status.author.screen_name,
                "created_at": status.created_at.isoformat(),
                "timestamp_ms": status.timestamp_ms,
                "url": "https://twitter.com/%s/status/%s" % (status.author.screen_name, status.id_str),
                "text": status.text,
                "hashtags": [h['text'] for h in status.entities['hashtags']],
                "is_quote_status": status.is_quote_status,
                "retweet": status.retweeted or status.text[:3] == 'RT ',
                "urlPics": urlPics})
            dbTwit.execute("""INSERT INTO printout (srcType, jdoc) VALUES (
                (SELECT id FROM srcType WHERE shortName = "Twitter") , %s)""" , (jsonObject,))
            dbTwit.close()
        except Exception, e:
            print(e)
            pass
        else:
            print "Inserted a tweet from %s into the database." % status.author.screen_name.encode("utf-8")

    def on_error(self, status_code):
        print 'An error has occured! Status code = %s' % status_code
        if status_code == 420:
            #returning False in on_data disconnects the stream
            sys.stdout.write("""We are being rate limited by Twitter. 
                Be aware that they incorporate exponential backoff alg.\n""")
            return False
        return True  # keep stream alive

    def on_timeout(self):
        print 'Snoozing Zzzzzz'


auth = tweepy.auth.OAuthHandler(twitterConf['consumerKey'], twitterConf['consumerSecret'])
auth.set_access_token(twitterConf['accessTokenKey'], twitterConf['accessTokenSecret'])
stream = tweepy.Stream(auth, StreamWatcherListener(), timeout=None)

# our filter
stream.filter(track=twitterConf['filter'].split())