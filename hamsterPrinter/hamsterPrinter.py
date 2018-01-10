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

"""version 1.0 - feeder for the hamsterPrinter a SoMe etc. POS printer"""
class hamster:
    """Basic stuff like reading the cfg"""
    def readConfig(self, cfg='hamsterPrinter.cfg'):
        """Write newlines and optional cut paper"""
        from configparser import ConfigParser
        parser = ConfigParser()
        parser.read(cfg)
        return parser



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

    def combinePILObjects(self, imgArray, currentpxWidth, printerConf):
        """Combine objects and print them"""
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