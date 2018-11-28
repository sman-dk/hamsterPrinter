#!/usr/bin/python
# -*- coding: utf-8 -*-
from os.path import dirname, realpath, sep, pardir
import sys
import qrcode
from io import BytesIO
import Image
import ImageDraw
import time
import urllib2 # In python3 this is just urllib
from StringIO import StringIO
import json
from datetime import datetime
import ImageFont, ImageDraw, Image
from escpos.printer import Serial, Usb

"""Feeder for the hamsterPrinter a SoMe etc. POS printer"""
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
    def __init__(self, printerConf):
        self.p = Serial(devfile=printerConf['dev'], 
            baudrate=[int(printerConf['baudrate']) if 'baudrate' in printerConf else 9600][0])
        self.p.open()
        self.printerWidth = printerConf['printerWidth']
        self.basedir = dirname(realpath(__file__)) + sep + pardir + sep
        self.printerConf = printerConf

    def imBox(self, width, height):
        """Create a white rectangle"""
        img = Image.new("1", (width, height))
        draw = ImageDraw.Draw(img)
        bgColor=255
        draw.rectangle((0,0) + img.size,fill=bgColor)
        return img

    def imText(self, text, align="left", 
        textSize=None, rotate=None, bgColor=255, fontColor=0, scale=None, 
        leading=0.25, txtWidth=None):
        """Render an image using a truetype font. Text may be be a list of string
        objects (one object per line). If a line is too wide the function will try to line wrap.
        Arg. 'leading' is the interline spacing in as a proportion of the height of a line.
        Arg. 'scale' is the proportion of the width of the paper."""
        if not textSize:
            textSize = int(self.printerConf['textSize'])
        if not txtWidth:
            txtWidth = self.printerConf['printerWidth']
        font = ImageFont.truetype(self.printerConf['fontFile'], textSize)

        def splitList(txtWidth, txtList, font, newlineSplitOnly=False):
            """Each str/unicode in txtList equals one line when printet. Split at newlines and furthermore split if a line is too wide."""
            # First of search for newlines and split the list if a newline is found
            withoutNewlines = []
            for txt in txtList:
                withoutNewlines.extend(txt.split("\n"))
            txtList = withoutNewlines
            if newlineSplitOnly:
                return txtList

            txtListWrapped = []
            for txt in txtList:
                # If the whole line is too wide, remove words until we are good
                if font.getsize(txt)[0] > txtWidth:
                    txtLen = len(txt)
                    for i in range(txtLen)[::-1]:
                        if font.getsize(txt[:i+1])[0] <= txtWidth:
                            whitespaceEtc = [ " ", "\t", "-" ]
                            if txt[i] in whitespaceEtc:
                                txtSplit = [ txt[:i+1].rstrip(), txt[i+1:] ]
                                if font.getsize(txtSplit[1])[0] > txtWidth:
                                    txtSplit = splitList(txtWidth, txtSplit, font)
                                    break
                                else:
                                    break
                            # If there are no whitespaces etc. then split the word
                            elif not any(w in txt[:i+1] for w in whitespaceEtc):
                                if font.getsize(txt[:i+1]+"-")[0] <= txtWidth:
                                    txtSplit = [ txt[:i+1].rstrip()+"-", txt[i+1:] ]
                                    if font.getsize(txtSplit[1])[0] > txtWidth:
                                        txtSplit = splitList(txtWidth, txtSplit, font)
                                        break
                                    else:
                                        break
                            else:
                                continue
                else:
                    txtSplit = [ txt ]
                txtListWrapped.extend(txtSplit)
            return txtListWrapped

        # If txtList is a simple string make it a list
        if type(text) is list:
            txtList = text
        else:
            txtList = [ text ]
        # Spacing between lines as a proportion of the width of a danish letter for the current text size.
        leadingDots = int(font.getsize(u"Å")[0]*leading)
        if rotate in [ 90, 270 ]:
            # Don't wrap lines based on width when turned 90 or 270 degrees
            txtList = splitList(txtWidth, txtList, font, newlineSplitOnly=True)
        else:
            # Do wordwrapping etc.
            txtList = splitList(txtWidth, txtList, font)

        # Determine the size of the resulting text image
        size = [0,0]
        lineHeight = font.getsize("a")[1]
        size = [ 0, ( leadingDots + lineHeight ) * len(txtList) + leadingDots]
        # Find the width
        if rotate is 180:
            # Avoid right alignment of rotated text, if a line is less wide than the paper / printerConf['printerWidth']
            size[0] = self.printerConf['printerWidth']
        else:
            for txt in txtList:
                maxWidth = font.getsize(txt)[0]
                if maxWidth > size[0]:
                    size[0] = maxWidth
        # Create the actual image containing the text
        img = Image.new("1",size)
        draw = ImageDraw.Draw(img)
        draw.rectangle((0,0) + img.size,fill=bgColor)
        pointer = [0, 0]
        # For each line..
        for txt in txtList:
            txtPxWidth = font.getsize(txt)[0]
            if align == "left":
                pointer[0] = 0
            elif align == "right":
                pointer[0] = size[0] - txtPxWidth
            elif align == "center":
                pointer[0] = (size[0] - txtPxWidth)/2
            draw.text(pointer, txt, font=font, fill=fontColor)
            pointer[1] += lineHeight + leadingDots

        if rotate:
            angles = [0, 90, 180, 270]
            if rotate in angles:
                img = img.rotate(rotate, expand=True)
            else:
                raise ValueError("rotate must be part of %s if set " % str(angles))
        if rotate in [90, 270]:
            if img.size[0] > self.printerConf['printerWidth'] and not scale:
                raise Exception("The textSize is too large to print. Use either a smaller textSize or the scale parameter")
        else:
            if img.size[0] > self.printerConf['printerWidth']:
                raise Exception("Could not print the text. One or more lines are too wide. Did you choose a very large font?")

        if align is not "left":
            imgOld = img
            img = Image.new("1",(txtWidth,imgOld.size[1]))
            draw = ImageDraw.Draw(img)
            draw.rectangle((0,0) + img.size,fill=bgColor)
            pointer = [0, 0]
            if align is "center":
                i = 2
            else:
                i = 1
            img.paste(imgOld,((txtWidth-imgOld.size[0])/i,0))
        return img

    def printLine(self, pxWidth=False, width=1.0, pxThickness=4, pxHeading=10, pxTrailing=10):
        """Prints a horisontal line.
        If width is set then pxWidth is ignored. width higher than 1.0 is ignored."""
        # calculate dimensions
        if not pxWidth:
            pxWidth = int(self.printerConf['printerWidth'] * width)
        pxHeight = pxHeading + pxThickness + pxTrailing
        img = Image.new("1", (self.printerConf['printerWidth'], pxHeight))
        draw = ImageDraw.Draw(img)
        draw.rectangle((0,0,self.printerConf['printerWidth'], pxHeight), fill=255)
        draw.rectangle(((self.printerConf['printerWidth'] - pxWidth)/2,pxHeading,
            (self.printerConf['printerWidth'] - pxWidth)/2 + pxWidth,pxHeading+pxThickness), fill=0)
        return img

    def combinePILObjects(self, imgArray, doPrint=True, multiCol=False, ignoreRotate=False):
        """Combine objects and print them"""
        if multiCol:
            # Multiple columns object (e.g. printing wearther forecast). imgArray is then an array of arrays.
            imArray = [ self.combinePILObjects(i, doPrint=False, ignoreRotate=True) for i in imgArray]
            # Determine height pre multicol
            orgMaxHeight=0
            for im in imArray:
                h = im[0].size[1]
                if h > orgMaxHeight:
                    orgMaxHeight = h
            numCols = len(imArray)
            imgMaster = self.imBox(self.printerConf['printerWidth'], orgMaxHeight/numCols)
            # Paste the columns together
            offset = 0
            numCols = len(imArray)
            colWidth = self.printerConf['printerWidth'] / numCols
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
                if img.size[0] > self.printerConf['printerWidth']:
                    # resize image
                    imgArray[i] = img.resize([self.printerConf['printerWidth'],
                        int(img.size[1]*float(self.printerConf['printerWidth'])/img.size[0])])
                height += imgArray[i].size[1]
            # Create 
            imgMaster = self.imBox(self.printerConf['printerWidth'], height)
            offset = 0
            for img in imgArray:
                imgMaster.paste(img,(0,offset))
                offset += img.size[1]
            if self.printerConf['rotate'] and not ignoreRotate:
                imgMaster = imgMaster.rotate(180)

        height = imgMaster.size[1]
        bytes_io = BytesIO()
        imgMaster.save(bytes_io, format="PNG")
        bytes_io.seek(0)
        imgData = bytes_io.read()
        if doPrint:
            bytes_io.seek(0)
            self.p.image(bytes_io, impl=self.printerConf['printType'])
        # return: PIL-object, height (int), PNG-file
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

    def commonPrint(self, conn, srcType):
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
                printFunc = getattr(self, srcType.lower())
                printData = printFunc(data)
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

    def twitter(self, twitterData):
        """Construct image with the tweet and print it"""
        # Create an array of PIL objects
        imgArray = []
        iconHeight = 120
        imgQR = self.qrIcon(twitterData['url'], size=iconHeight)
        imgTwit = Image.open(dirname(realpath(__file__)) + sep + pardir + sep + 
            "/artwork/SoMe/agata/twitter.png").convert("1")
        imgTwit = imgTwit.resize([iconHeight-2*4,iconHeight-2*4]) # QR has a border of 4
        #headTxt = "%s @%s %s\n%s" % (twitterData['name'], twitterData['screen_name'], 
        #    [ "retweeted" if twitterData['retweet'] else "tweeted"][0], twitterData['created_at'][:-3])
        headTxt = "%s %s\n%s" % (twitterData['name'], 
            [ "retweeted" if twitterData['retweet'] else "tweeted"][0], twitterData['created_at'][:-3])
        imHeadTxtWidth = self.printerConf['printerWidth'] - 2*iconHeight - 2 - 12
        # Insert PIL w text
        imHeadTxt = self.imText(headTxt, txtWidth=imHeadTxtWidth)
        imHeader = self.imBox(self.printerConf['printerWidth'], 
            [ imHeadTxt.size[1] if imHeadTxt.size[1] > iconHeight else iconHeight][0]+4+9)
        # Paste them together
        imHeader.paste(imgTwit,(0,4))
        imHeader.paste(imHeadTxt,(iconHeight+12,4))
        imHeader.paste(imgQR,(iconHeight+2+imHeadTxtWidth+2,0))
        imgArray.append(imHeader)
        imgArray.append(self.imText(twitterData['text']))
        # Add images
        for url in twitterData['urlPics']:
            try:
                url = urllib2.urlopen(url, timeout=10)
                f = StringIO()
                responseIO = StringIO(url.read())
                im = Image.open(responseIO).convert("1")
                imgArray.append(self.imBox(self.printerConf['printerWidth'], 10))
                imgArray.append(im)
                imgArray.append(self.imBox(self.printerConf['printerWidth'], 10))
            except Exception, e:
                print(e)
                errorText = "Hrmpf... Failed to download picture from Twitter at print time. See the log for details."
                imgArray.append(self.imText(errorText, bgColor=0, fontColor=255))
        imgArray.append(self.printLine())

        # print it 
        imgMaster, height, imgData = self.combinePILObjects(imgArray)        
        return (height, imgData, [0 if not self.printerConf['rotate'] else 1][0], "image/png")

    def weatherCloud(self, weatherData, dayType, widthDiv=1.3):
        basedir=self.basedir + "artwork/weather/georg"
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

        imWidth=int(self.printerConf['printerWidth']/widthDiv)

        im = im.resize([imWidth,int(float(imWidth)/im.size[0]*im.size[1])])
        imCloud = self.imBox(self.printerConf['printerWidth'], im.size[0])
        imCloud.paste(im,((self.printerConf['printerWidth']-imWidth)/2,0))
        return imCloud

    def weathercurrent(self, weatherData):
        imgArray = []
        imgArray.append(self.imText('Current weather', align="center", textSize=60))
        imgArray.append(self.imText("%s %s" % 
            (weatherData['current']['last_updated'],
            weatherData['location']['name']) , align="center"))
        imCloud = self.weatherCloud(weatherData, 'current')
        imgArray.append(imCloud)
        imgArray.append(self.imText(
            weatherData['current']['condition']['text'], align="center", textSize=40))
        imgArray.append(self.imText(u'%.1f\xb0' % 
            weatherData['current']['temp_c'], align="center", textSize=120))
        # Wind speed + direction
        mps = weatherData['current']['wind_kph']/3.6
        imWindText = self.imText('%.1f m/s' % mps, align="left", textSize=40)
        basedir=self.basedir + "artwork/weather/georg"
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
            centeredImWind = self.imBox(self.printerConf['printerWidth'],imWind.size[1])
            centeredImWind.paste(imWind,[(self.printerConf['printerWidth']-imWind.size[0])/2,0])
        imgArray.append(centeredImWind)
        imgArray.append(self.imText(
            "%i%% rel.   %.0f mPa   temp. feels like %i\xb0" %
            (weatherData['current']['humidity'], weatherData['current']['pressure_mb'], 
            weatherData['current']['feelslike_c']), align="center"))
        imgArray.append(self.printLine())
        imgMaster, height, imgData = self.combinePILObjects(imgArray)    
        return (height, imgData, [0 if not self.printerConf['rotate'] else 1][0], "image/png")

    def weatherforecast(self, weatherData):
        # Header: "Weather forecast", date etc.
        imgArray = []
        imgArray.append(self.imText('Weather forecast', align="center", textSize=60))
        imgArray.append(self.imText("%s %s" % 
            (weatherData['current']['last_updated'],
            weatherData['location']['name']) , align="center"))
        imgArray.append(self.imBox(20,20)) # some blank space / "new line"

        # The forecast in multiple columns
        imgSuperArray = []
        for day in weatherData['forecast']['forecastday']:
            imArrayDay = []
            # Weekday
            #dayTxt = [ "Today" if day['date'] == datetime.now().isoformat().split('T')[0] else datetime.fromtimestamp(date['date_epoch']).strftime('%A')[0]
            dayTxt = datetime.fromtimestamp(day['date_epoch']).strftime('%A')#[:3]
            imArrayDay.append(self.imText(dayTxt, align="center", textSize=130))
            # Weather cloud
            imCloud = self.weatherCloud(day, 'day', widthDiv=1)
            imArrayDay.append(imCloud)
            # Forecast text
            # Blank spaces are added to ensure line break, if a text is too short to expand to multiple lines
            # FIXME does not seem to work as it should
            forecastTxt = "{:<16}".format(day['day']['condition']['text'])
            imArrayDay.append(self.imText(
            forecastTxt, align="center", textSize=90))
            # Temperature etc.
            imArrayDay.append(self.imText(u'%.1f\xb0' % 
            day['day']['maxtemp_c'], align="center", textSize=180))
            windSpeed = day['day']['maxwind_kph']/3.6
            imArrayDay.append(self.imText(u'avg %.1f\xb0\nmin %.1f\xb0\nmax %.1f m/s' % 
            (day['day']['avgtemp_c'],day['day']['mintemp_c'],windSpeed), align="center", textSize=80))
            # Append daily forecast to mulicolumn forecast
            imgSuperArray.append(imArrayDay)
        # Combine multicolumn forecast to one object
        imgColumns, height, imgData = self.combinePILObjects(imgSuperArray, multiCol=True)
        # Append multicolumn forecast to what is to be printed
        imgArray.append(imgColumns)
        imgArray.append(self.printLine())
        # Create the final image
        imgMaster, height, imgData = self.combinePILObjects(imgArray) 
        return (height, imgData, [0 if not self.printerConf['rotate'] else 1][0], "image/png")
