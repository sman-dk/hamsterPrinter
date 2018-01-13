# Social Media Hamster Printer
*OBS This is still in early development stages. Wait a few days/weeks and check back in to see if this message has been removed :-)*

Prints messages from social media (Facebook, Twitter etc.) and other sources on a POS/receipt printer

The software has been tested on Debian/Ubuntu.

## Overview

The software consists of a number of applications (one for each source type) that feed a MySQL database with data and an application that formats and prints the data. I use daemontools for running the processes and keeping them alive.

E.g. 
twitter.py \  
facebook.py ----> MySQL ---> printer.py  ---> USB POS printer ---> Awesome printing  
weather.py /

## Supported inputs / feeders
Twitter is real time. Facebook and Instagram is updated regularly by polling their services.
* Twitter
* Facebook (Not yet supported)
* Instagram (Not yet supported)
* Weather from Apixu.com

## Installation guide
`apt-get install mysql-server`

### Create the database schema
```CREATE DATABASE hamsterprinter CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
create user printer;
grant all on hamsterprinter.* to 'printer'@'localhost' identified by 'awesomePassphrase';
create user feeder;
grant all on hamsterprinter.* to 'feeder'@'localhost' identified by 'awesomePassphrase';
use hamsterprinter;
FLUSH PRIVILEGES;
CREATE TABLE printout (id int NOT NULL AUTO_INCREMENT, dt DATETIME DEFAULT CURRENT_TIMESTAMP, printed BOOLEAN NOT NULL DEFAULT 0, srcType int NOT NULL, height INT DEFAULT NULL, printedImg MEDIUMBLOB DEFAULT NULL, printedImgRotated BOOLEAN DEFAULT 0, printedImgMimeType VARCHAR(30) DEFAULT NULL, jdoc JSON , PRIMARY KEY(ID));
CREATE INDEX idx_printout ON printout(dt, printed, srcType, height, printedImgMimeType);
CREATE TABLE srcType (id int NOT NULL, shortName VARCHAR(32), comment VARCHAR(100), PRIMARY KEY(ID));```
```INSERT INTO srcType (id, shortName) VALUES(1, "Twitter");
INSERT INTO srcType (id, shortName) VALUES(2, "Facebook");
INSERT INTO srcType (id, shortName) VALUES(3, "Instagram");
INSERT INTO srcType (id, shortName) VALUES(4, "WeatherForecast");
INSERT INTO srcType (id, shortName) VALUES(5, "WeatherCurrent");```

### Software and dependencies:
```git clone https://github.com/sman-dk/pyPOSprinter.git
git clone https://github.com/sman-dk/hamsterPrinter.git```
pyPOSprinter is used to talk to the printer and hamsterPrinter expect it to be placed in a folder next to hamsterPrinter as in the above example.

```sudo apt-get install libmysqlclient-dev python-pip
sudo pip install tweepy mysql-python argparse configparser qrcode Pillow schedule```

### Configuration ###
Adjust hamsterPrinter.cfg to your needs and run the instances (printer.py, twitter.py etc.) by hand to see if everything works as intended.

### Keeping the software running
You can use whatever tool you like to keep the processes running. I use the package daemontools as it daemonizes a process in an easy way.
`sudo apt-get install daemontools daemontools-run`
```sudo -s
BASEDIR=/home/hamster # Adjust to your neeeds
USERNAME=hamster # The user the
APPDIR=${BASEDIR}/hamsterPrinter
DAEMONTOOLSDIR=${BASEDIR}/service
usermod -a -G dialout ${USERNAME}
mkdir $DAEMONTOOLSDIR
mkdir 
for i in twitter facebook instagram weather
do
    mkdir ${BASEDIR}/$i
    mkdir ${BASEDIR/${i}/log
    echo "#!/bin/bash
echo starting ${i}.py
exec setuidgid ${USERNAME} ${APPDIR}/${i}.py" > ${DAEMONTOOLSDIR}/${i}/run
    echo "#!/bin/bash
# log in 1MB logfiles
exec multilog t s1048576 ./main" > ${DAEMONTOOLSDIR}/${i}/log/run
    chmod +x ${DAEMONTOOLSDIR}/${i}/run
    chmod +x ${DAEMONTOOLSDIR}/${i}/log/run
    ln -s ${DAEMONTOOLSDIR}/${i} /etc/service/${i}
done
initctl start svscan```

#### Quick cheat sheet for daemontools
Status for an individual service (e.g. printer.py):
`svstat /etc/service/printer`
Status for all services:
`svstat /etc/service/*`
Stop a service:
`svc -d /etc/service/printer`
Stop all services
`svc -d /etc/service/*`
Starting a service: svc -u <path>

Tailing a log (daemontools has its own log format):
tail -f /etc/service/printer/log/main/current | tai64nlocal
Tailing all the logs:
tail -f /etc/service/*/log/main/current | tai64nlocal
