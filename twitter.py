#!/usr/bin/python
# -*- coding: utf-8 -*-

from hamsterPrinter import hamsterPrinter
import argparse
import sys
import tweepy
import atexit
import time
import json
import MySQLdb
from os.path import dirname, realpath, sep, pardir
basedir=dirname(realpath(__file__)) + sep
# Argument parsing

parser = argparse.ArgumentParser(description='Twitter feeder for hamsterPrinter')
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

# Load twitter config
keys = ['consumerKey', 'consumerSecret', 'accessTokenKey', 'accessTokenSecret', 'filter']
twitterConf = {}
for k in keys:
    twitterConf[k] = cfg.get('twitter', k)

optionalKeys = ['follow', 'filter']
for k in optionalKeys:
    try:
        twitterConf[k] = cfg.get('twitter', k)
    except:
        pass

# Twitter streaming stuff
class StreamWatcherListener(tweepy.StreamListener):
    # Run when a Twitter status matches the filter
    def on_status(self, status):
        # Filter out the messages we want. This way we can actually follow
        # a user without getting al the retweets and messages target at that user
        filterOk = False
        # If we want something from this author
        if status.author.id_str in userIdList:
            filterOk = True
        # If we want something from this hashtag
        elif 'filter' in twitterConf:
            hashTags = twitterConf['filter'].split()
            for h in hashTags:
                if h + " " in status.text or "@" + h[1:] + " " in status.text:
                    filterOk = True
                elif h[1:] in [ht['text'] for ht in status.entities['hashtags']]:
                    filterOk = True
        if filterOk:
            try:
                hasPics = False
                dbTwit = conn.cursor()
                if 'extended_entities' in dir(status):
                    hasPics = True
                    urlPics = [ media['media_url'] for media in status.extended_entities['media']]
                else:
                    urlPics = [] 
                jsonObject = json.dumps({
                    "name": status.author.name,
                    "userId": status.author.id_str,
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
        # https://developer.twitter.com/en/docs/basics/response-codes
        if status_code == 420 or status_code == 429:
            #returning False in on_data disconnects the stream
            sys.stdout.write("""We are being rate limited by Twitter. We are 
                now sleeping for 900 seconds and hope to get back to being in 
                good standing. Read more about the 15 minute windows at 
                https://developer.twitter.com/en/docs/basics/rate-limiting\n""")
            time.sleep(900)
            return False
        return True  # keep stream alive

    def on_timeout(self):
        print 'Snoozing Zzzzzz'


auth = tweepy.auth.OAuthHandler(twitterConf['consumerKey'], twitterConf['consumerSecret'])
auth.set_access_token(twitterConf['accessTokenKey'], twitterConf['accessTokenSecret'])
stream = tweepy.Stream(auth, StreamWatcherListener(), timeout=None)

userIdList = []
if 'follow' in twitterConf:
    usernameList = twitterConf['follow'].split()
    for username in usernameList:
        user = tweepy.API(auth).get_user(username)
        userIdList.append(str(user.id))
        print "Looked up id for user %s and got id %i. Will now follow on Twitter." % (username,user.id)
    if len(userIdList) > 0:
        twitterConf['followIds'] = userIdList

# our filter
stream.filter(
    track=[ twitterConf['filter'].split() if 'filter' in twitterConf else None][0],
    follow=[ twitterConf['followIds'] if 'followIds' in twitterConf else None][0])