#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '../pyPOSprinter')
import qrcode
from io import BytesIO
import Image
import ImageDraw
import time
import urllib2 # In python3 this is just urllib
from StringIO import StringIO
import json
from datetime import datetime

"""version 1.0 - feeder for the hamsterPrinter a SoMe etc. POS printer"""
class hamster:
    """Basic stuff like reading the cfg and other common stuff"""
    def readConfig(self, cfg='hamsterPrinter.cfg'):
        """Write newlines and optional cut paper"""
        from configparser import ConfigParser
        parser = ConfigParser()
        parser.read(cfg)
        return parser

    def pinAgain(self, weatherType, dbObj, chuteLengthPx, cfg):
        """Function to check if a "pinned" message/whatever should be printed again"""
        printFeeds = [ i.lower() for i in cfg.get('printer', 'printFeeds').split()]
        printout = []
        # If the printer is too much behind we wait with the pinning
        try:
            dbWeather = dbObj.cursor()
            dbWeather.execute("""SELECT srcType.shortName, printout.height 
                FROM printout INNER JOIN srcType 
                ON srcType.id = printout.srcType 
                ORDER BY printout.id DESC LIMIT 100""")
            px=0
            while True:
                try:
                    row = dbWeather.fetchone()
                    # If there are no more rows to fetch
                    if row == None:
                        break
                    srcType, height = row
                    # Only include sources that are active on the printer
                    if srcType.lower() not in printFeeds and 'all' not in printFeeds:
                        continue
                    if height is None:
                        print("""The printer is behind with its printing. Waiting with pinning message of type %s""" % weatherType)
                        return False
                    else:
                        px += height
                        if px > chuteLengthPx:
                            # We have fetched enough now
                            break
                    printout.append({"srcType": srcType, "height": height})
                except Exception, e:
                    print(e)
                    break  
            dbWeather.close()     
        except Exception, e:
            print(e)
            pass
        # Find out if it is about time to print something new
        aboutTime = True
        for p in printout:
            if p['srcType'] == weatherType:
                aboutTime = False
        # If nothing has been printed yet
        if len(printout) is 0:
            print printout
            print "Nothing has been printed by the printer so we are not pinning anything yet."
            aboutTime = False
        if aboutTime:
            print """The pinned message of type %s has been swapped out of the chute. Lets add it again!""" % weatherType
            return True
        else:
            return False


class printout:
    """Print stuff from Twitter"""
    def __init__(self, posprinter):
        self.posprinter = posprinter

    def imBox(self, width, height):
        """Create a white rectangle"""
        img = Image.new("1", (width, height))
        draw = ImageDraw.Draw(img)
        bgColor=255
        draw.rectangle((0,0) + img.size,fill=bgColor)
        return img

    def combinePILObjects(self, imgArray, currentpxWidth, printerConf, doPrint=True, multiCol=False):
        """Combine objects and print them"""
        if multiCol:
            # Multiple columns object (e.g. printing wearther forecast). imgArray is then an array of arrays.
            imArray = [ self.combinePILObjects(i, currentpxWidth, printerConf, doPrint=False) for i in imgArray]
            # Determine height pre multicol
            orgMaxHeight=0
            for im in imArray:
                h = im[0].size[1]
                if h > orgMaxHeight:
                    orgMaxHeight = h
            numCols = len(imArray)
            imgMaster = self.imBox(currentpxWidth, orgMaxHeight/numCols)
            # Paste the columns together
            offset = 0
            numCols = len(imArray)
            colWidth = currentpxWidth / numCols
            for i in imArray:
                imgMaster.paste(i[0].resize([colWidth, int(i[0].size[1]*1./numCols)]),(offset,0))
                offset += colWidth  
        else:
            # Calculate height
            height = 0
            imgTooWide=False
            for i in range(len(imgArray)):
                img = imgArray[i]
                # If an image is too large
                if img.size[0] > currentpxWidth:
                    # resize image
                    imgArray[i] = img.resize([currentpxWidth,int(img.size[1]*float(currentpxWidth)/img.size[0])])
                height += imgArray[i].size[1]
            # Create 
            imgMaster = self.imBox(currentpxWidth, height)
            offset = 0
            for img in imgArray:
                imgMaster.paste(img,(0,offset))
                offset += img.size[1]
            if printerConf['rotate']:
                imgMaster = imgMaster.rotate(180)

        height = imgMaster.size[1]
        bytes_io = BytesIO()
        imgMaster.save(bytes_io, format="PNG")
        bytes_io.seek(0)
        imgData = bytes_io.read()
        if doPrint:
            self.posprinter.printImgFromPILObject(imgMaster)
        return(imgMaster, height, imgData)

    def qrIcon(self, url, size=120):
        iconHeight = size
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image()
        return img.resize((iconHeight,iconHeight))

    def commonPrint(self, conn, srcType, currentpxWidth, printerConf):
        try:
            dbPrinter = conn.cursor()
            dbPrinter.execute("""SELECT printout.id, printout.jdoc 
                FROM printout INNER JOIN srcType 
                ON srcType.id = printout.srcType 
                WHERE srcType.shortName = %s AND printed = 0
                ORDER BY printout.id ASC LIMIT 1""", (srcType,))
            row = dbPrinter.fetchone()
            # if there is something unprinted waiting for us for the given srcType
            if row is not None:
                data = json.loads(row[1])
                hest = getattr(self, srcType.lower())
                printData = hest(data, currentpxWidth, printerConf)
                # Hmm. one could argue that if printing something fails, 
                # then the message should not be marked as printed in the db..
                dbPrinter.execute("""UPDATE printout SET height = %s, 
                    printed = 1, printedImg = _binary %s, printedImgRotated = %s, 
                    printedImgMimeType = %s WHERE id=%s""", (str(printData[0]),
                    printData[1], str(printData[2]),
                    printData[3], str(row[0])))
            dbPrinter.close()
        except Exception, e:
            print(e)
            try:
                print("The id for the failed message in the printout table: %i" % row[0])
            except:
                pass
        else:
            if row is not None:
                if srcType is "Twitter":
                    print("Printed a twitter message from %s to the printer".encode('utf-8') % data['screen_name'])
                if srcType is "WeatherCurrent":
                    print("Printed a WeatherCurrent message")
                if srcType is "WeatherForecast": 
                    print("Printed a WeatherForecast message")

    def twitter(self, twitterData, currentpxWidth, printerConf):
        """Construct image with the tweet and print it"""
        # Create an array of PIL objects
        imgArray = []

        iconHeight = 120
        imgQR = self.qrIcon(twitterData['url'], size=iconHeight)
        imgTwit = Image.open("/home/georg/hamster/hamsterPrinter/artwork/SoMe/agata/twitter.png").convert("1")
        imgTwit = imgTwit.resize([iconHeight-2*4,iconHeight-2*4]) # QR has a border of 4
        headTxt = "%s @%s %s\n%s" % (twitterData['name'], twitterData['screen_name'], [ "retweeted" if twitterData['retweet'] else "tweeted"][0], twitterData['created_at'])
        imHeadTxtWidth = currentpxWidth - 2*iconHeight - 2 - 12
        # Insert PIL w text
        imHeadTxt = self.posprinter.printFontText(headTxt, align="left", 
            fontFile=printerConf['fontFile'], 
            textSize=printerConf['textSize'], leading=0.25, returnPILObject=True, txtWidth=imHeadTxtWidth, dontPrint=True)
        imHeader = self.imBox(currentpxWidth, 
            [ imHeadTxt.size[1] if imHeadTxt.size[1] > iconHeight else iconHeight][0]+4+9)
        # Paste them together
        imHeader.paste(imgTwit,(0,4))
        imHeader.paste(imHeadTxt,(iconHeight+12,4))
        imHeader.paste(imgQR,(iconHeight+2+imHeadTxtWidth+2,0))
        imgArray.append(imHeader)
        imgArray.append(self.posprinter.printFontText(twitterData['text'], align="left", 
            fontFile=printerConf['fontFile'], textSize=printerConf['textSize'], 
            leading=0.25, returnPILObject=True, dontPrint=True))
        # Add images
        for url in twitterData['urlPics']:
            try:
                url = urllib2.urlopen(url, timeout=10)
                f = StringIO()
                responseIO = StringIO(url.read())
                im = Image.open(responseIO).convert("1")
                imgArray.append(self.imBox(currentpxWidth, 10))
                imgArray.append(im)
                imgArray.append(self.imBox(currentpxWidth, 10))
            except Exception, e:
                print(e)
                errorText = "Hrmpf... Failed to download picture from Twitter at print time. See the log for details."
                imgArray.append(self.posprinter.printFontText(errorText, align="left", 
                    fontFile=printerConf['fontFile'], textSize=printerConf['textSize'], 
                    leading=0.25, returnPILObject=True, dontPrint=True, bgColor=0, fontColor=255))
        imgArray.append(self.posprinter.printLine(returnPILObject=True, dontPrint=True))

        # print it 
        imgMaster, height, imgData = self.combinePILObjects(imgArray, currentpxWidth, printerConf)        
        return (height, imgData, [0 if not printerConf['rotate'] else 1][0], "image/png")

    def weatherCloud(self, weatherData, currentpxWidth, dayType, widthDiv=1.3):
        basedir="artwork/weather/georg"
        if dayType == "current":
            dayOrNight = [ "day" if weatherData['current']['is_day'] is 1 else "night"][0]
        else:
            dayOrNight = "day"
        try:
            filePath = "%s/%s/%s.png" % (basedir,dayOrNight,weatherData[dayType]['condition']['code'])
            im = Image.open(filePath,'r').convert("1")
        except:
            try:
                filePathUnknown = "%s/%s/unknown.png" % (basedir,dayOrNight)
                im = Image.open(filePathUnknown,'r').convert("1")
            except Exception, e:
                print "Hmm. It seems we could not read %s or %s in the same folder" % (filePath, filePathUnknown)
                print(e)
                raise
        imWidth=int(currentpxWidth/widthDiv)
        im = im.resize([imWidth,int(float(imWidth)/im.size[0]*im.size[1])])
        imCloud = self.imBox(currentpxWidth, im.size[0])
        imCloud.paste(im,((currentpxWidth-imWidth)/2,0))
        return imCloud

    def weathercurrent(self, weatherData, currentpxWidth, printerConf):
        imgArray = []
        imgArray.append(self.posprinter.printFontText('Current weather', align="center", 
            fontFile=printerConf['fontFile'], textSize=60, 
            leading=0.25, returnPILObject=True, dontPrint=True))
        imgArray.append(self.posprinter.printFontText("%s %s" % 
            (weatherData['current']['last_updated'],
            weatherData['location']['name']) , align="center", 
            fontFile=printerConf['fontFile'], textSize=30, 
            leading=0.25, returnPILObject=True, dontPrint=True))
        imCloud = self.weatherCloud(weatherData, currentpxWidth, dayType='current')
        imgArray.append(imCloud)
        imgArray.append(self.posprinter.printFontText(
            weatherData['current']['condition']['text'], align="center", 
            fontFile=printerConf['fontFile'], textSize=40, 
            leading=0.25, returnPILObject=True, dontPrint=True))
        imgArray.append(self.posprinter.printFontText(u'%.1f\xb0' % 
            weatherData['current']['temp_c'], align="center", 
            fontFile=printerConf['fontFile'], textSize=120, 
            leading=0.25, returnPILObject=True, dontPrint=True))
        # Wind speed + direction
        mps = weatherData['current']['wind_kph']/3.6
        imWindText = self.posprinter.printFontText('%.1f m/s' % mps, align="left", 
            fontFile=printerConf['fontFile'], textSize=40, 
            leading=0.25, returnPILObject=True, dontPrint=True)
        basedir="artwork/weather/georg"
        dayOrNight = [ "day" if weatherData['current']['is_day'] is 1 else "night"][0]
        try:
            filePath = "%s/%s/arrow.png" % (basedir,dayOrNight)
            imArrow = Image.open(filePath,'r')
        except Exception, e:
            print(e)
            raise
        else:
            imArrow = imArrow.rotate(weatherData['current']['wind_degree'], expand=True)
            arrowWidth = 70
            imArrow = imArrow.resize([arrowWidth,int(float(arrowWidth)/imArrow.size[0]*
                imArrow.size[1])]).convert("1")
            imWind = self.imBox(imWindText.size[0]+imArrow.size[0],
                [ imArrow.size[1] if imArrow.size[1] > imArrow.size[0] 
                    else imArrow.size[0]][0])
            imWind.paste(imWindText,(0,0))
            imWind.paste(imArrow,(imWindText.size[0]+10,0))
            centeredImWind = self.imBox(currentpxWidth,imWind.size[1])
            centeredImWind.paste(imWind,[(currentpxWidth-imWind.size[0])/2,0])
        imgArray.append(centeredImWind)
        imgArray.append(self.posprinter.printFontText(
            "%i%% rel.   %.0f mPa   temp. feels like %i\xb0" %
            (weatherData['current']['humidity'], weatherData['current']['pressure_mb'], 
            weatherData['current']['feelslike_c']), align="center", 
            fontFile=printerConf['fontFile'], textSize=30,
            leading=0.25, returnPILObject=True, dontPrint=True))
        imgArray.append(self.posprinter.printLine(returnPILObject=True, dontPrint=True))
        imgMaster, height, imgData = self.combinePILObjects(imgArray, currentpxWidth, printerConf)    
        return (height, imgData, [0 if not printerConf['rotate'] else 1][0], "image/png")

    def weatherforecast(self, weatherData, currentpxWidth, printerConf):
        imgArray = []
        imgArray.append(self.posprinter.printFontText('Weather forecast', align="center", 
            fontFile=printerConf['fontFile'], textSize=60, 
            leading=0.25, returnPILObject=True, dontPrint=True))
        imgArray.append(self.posprinter.printFontText("%s %s" % 
            (weatherData['current']['last_updated'],
            weatherData['location']['name']) , align="center", 
            fontFile=printerConf['fontFile'], textSize=30, 
            leading=0.25, returnPILObject=True, dontPrint=True))
        imgArray.append(self.imBox(20,20)) # some blank space / "new line"
        # The forecast in multiple columns
        imgSuperArray = []
        for day in weatherData['forecast']['forecastday']:
            imArrayDay = []
            #dayTxt = [ "Today" if day['date'] == datetime.now().isoformat().split('T')[0] else datetime.fromtimestamp(date['date_epoch']).strftime('%A')[0]
            dayTxt = datetime.fromtimestamp(day['date_epoch']).strftime('%A')#[:3]
            imArrayDay.append(self.posprinter.printFontText(dayTxt, 
            align="center", fontFile=printerConf['fontFile'], textSize=130, 
            leading=0.25, returnPILObject=True, dontPrint=True))
            imCloud = self.weatherCloud(day, currentpxWidth, dayType='day', widthDiv=1)
            imArrayDay.append(imCloud)
            # Forecast text
            # Add blank spaces to ensure line break, if a text is too short to expand to multiple lines
            # FIXME "center does not seem to work when there are line breaks"
            forecastTxt = "{:<16}".format(day['day']['condition']['text'])
            imArrayDay.append(self.posprinter.printFontText(
            forecastTxt, align="center", 
            fontFile=printerConf['fontFile'], textSize=90, 
            leading=0.25, returnPILObject=True, dontPrint=True))
            # Temperature
            imArrayDay.append(self.posprinter.printFontText(u'%.1f\xb0' % 
            day['day']['maxtemp_c'], align="center", 
            fontFile=printerConf['fontFile'], textSize=180, 
            leading=0.25, returnPILObject=True, dontPrint=True))
            windSpeed = day['day']['maxwind_kph']/3.6
            imArrayDay.append(self.posprinter.printFontText(u'avg %.1f\xb0\nmin %.1f\xb0\nmax %.1f m/s' % 
            (day['day']['avgtemp_c'],day['day']['mintemp_c'],windSpeed), align="center", 
            fontFile=printerConf['fontFile'], textSize=80, 
            leading=0.25, returnPILObject=True, dontPrint=True))
            imgSuperArray.append(imArrayDay)


        imgColumns, height, imgData = self.combinePILObjects(imgSuperArray, currentpxWidth, printerConf, doPrint=False, multiCol=True)
        imgArray.append(imgColumns)
        imgArray.append(self.posprinter.printLine(returnPILObject=True, dontPrint=True))
        imgMaster, height, imgData = self.combinePILObjects(imgArray, currentpxWidth, printerConf) 
        return (height, imgData, [0 if not printerConf['rotate'] else 1][0], "image/png")
