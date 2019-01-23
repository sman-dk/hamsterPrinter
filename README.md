# Social Media Hamster Printer
*OBS Facebook and Instagram support is still missing - but Twitter and weather forecast is implemented*

Prints messages from social media (Facebook, Twitter etc.) and other sources on a POS/receipt printer

The software has been tested on Debian/Ubuntu.

## Overview

The software consists of a number of applications (one for each source type) that feed a MySQL database with data and an application that formats and prints the data. In the example below I use systemd for running the processes and keeping them alive.

E.g.  
twitter.py ----> MySQL ---> printer.py  ---> USB POS printer ---> Awesome printing  
weather.py /

## Supported inputs / feeders
* Twitter
* Facebook (Not yet supported)
* Instagram (Not yet supported)
* Weather from Apixu.com

n.b. Twitter is using the real time streaming API. This free API does not have a guarantee that 100% of the messages are delivered. I.e. you may experience that a tweet is missing.

## Installation guide
You need a MySQL server
```
apt-get install mysql-server
```

### Create the database schema
Log in to mysql  
```
mysql -uroot -p
```

Then run the following (adjust with your desired password)
```
CREATE DATABASE hamsterprinter CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
create user printer;
grant all on hamsterprinter.* to 'printer'@'localhost' identified by 'awesomePassphrase';
create user feeder;
grant all on hamsterprinter.* to 'feeder'@'localhost' identified by 'awesomePassphrase';
use hamsterprinter;
FLUSH PRIVILEGES;
CREATE TABLE printout (id int NOT NULL AUTO_INCREMENT, dt DATETIME DEFAULT CURRENT_TIMESTAMP, printed BOOLEAN NOT NULL DEFAULT 0, srcType int NOT NULL, height INT DEFAULT NULL, printedImg MEDIUMBLOB DEFAULT NULL, printedImgRotated BOOLEAN DEFAULT 0, printedImgMimeType VARCHAR(30) DEFAULT NULL, jdoc JSON , PRIMARY KEY(ID));
CREATE INDEX idx_printout ON printout(dt, printed, srcType, height, printedImgMimeType);
CREATE TABLE srcType (id int NOT NULL, shortName VARCHAR(32), comment VARCHAR(100), PRIMARY KEY(ID));
```

```
INSERT INTO srcType (id, shortName) VALUES(1, "Twitter");
INSERT INTO srcType (id, shortName) VALUES(2, "Facebook");
INSERT INTO srcType (id, shortName) VALUES(3, "Instagram");
INSERT INTO srcType (id, shortName) VALUES(4, "WeatherForecast");
INSERT INTO srcType (id, shortName) VALUES(5, "WeatherCurrent");
```

### Software and dependencies:
In this example we place the software in /home/hamster
```
git clone https://github.com/sman-dk/hamsterPrinter.git
```
Dependencies
```
sudo apt-get install libmysqlclient-dev python-pip python-escpos
sudo pip install tweepy mysql-python argparse configparser qrcode Pillow schedule
```

### Configuration ###
Adjust hamsterPrinter.cfg to your needs and run the instances (printer.py, twitter.py etc.) by hand to see if everything works as intended.

### Keeping the software running using systemd
In this example the software is running in a Raspberry Pi running Raspbian (a Debian distribution). Adjust it to your setup:

/etc/systemd/system/twitter.service
```[Unit]
Description=twitter.py
After=network.target

[Service]
Type=simple
# Another Type option: forking
User=pi
ExecStart=/usr/bin/env python /home/pi/hamsterPrinter/twitter.py
Restart=always

[Install]
WantedBy=multi-user.target
```

/etc/systemd/system/printer.service
```[Unit]
Description=printer.py
After=network.target

[Service]
Type=simple
# Another Type option: forking
User=pi
ExecStart=/usr/bin/env python /home/pi/hamsterPrinter/printer.py
Restart=always

[Install]
WantedBy=multi-user.target
```

/etc/systemd/system/weather.service
```[Unit]
Description=weather.py
After=network.target

[Service]
Type=simple
# Another Type option: forking
User=pi
ExecStart=/usr/bin/env python /home/pi/hamsterPrinter/weather.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```systemctl enable twitter
systemctl enable printer
systemctl enable weather
systemctl start twitter
systemctl start printer
systemctl start weather
```
