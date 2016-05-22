import json
import urllib2
import hashlib
import struct
import sha
import os
import time
import sys
import ConfigParser
import logging


CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.ini")
CONF = ConfigParser.ConfigParser()
CONF.read(CONFIG_FILE)


class chbtcApi:
    def __init__(self):
        self._setupLogging()
        self.mykey = CONF.get("default", "access_key")
        self.mysecret = CONF.get("default", "secret_key")

        self.k1 = float(CONF.get("default", "k1"))
        self.k2 = float(CONF.get("default", "k2"))

        self.handledCny = float(CONF.get("default", "handle_cny"))

        self.cny = 0.0
        self.eth = 0.0

        self.syncBalanceIndex = 0
        self.last5mink = None

    def _setupLogging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s %(levelname)s %(message)s',
            datefmt='%a, %d %b %Y %H:%M:%S',
            filename='logchbtc.log',
            filemode='a')

        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        formatter = logging.Formatter('%(levelname)-8s %(message)s')
        console.setFormatter(formatter)
        logging.getLogger('').addHandler(console)

    def __fill(self, value, lenght, fillByte):
        if len(value) >= lenght:
            return value
        else:
            fillSize = lenght - len(value)
        return value + chr(fillByte) * fillSize

    def __doXOr(self, s, value):
        slist = list(s)
        for index in xrange(len(slist)):
            slist[index] = chr(ord(slist[index]) ^ value)
        return "".join(slist)

    def __hmacSign(self, aValue, aKey):
        keyb = struct.pack("%ds" % len(aKey), aKey)
        value = struct.pack("%ds" % len(aValue), aValue)
        k_ipad = self.__doXOr(keyb, 0x36)
        k_opad = self.__doXOr(keyb, 0x5c)
        k_ipad = self.__fill(k_ipad, 64, 54)
        k_opad = self.__fill(k_opad, 64, 92)
        m = hashlib.md5()
        m.update(k_ipad)
        m.update(value)
        dg = m.digest()

        m = hashlib.md5()
        m.update(k_opad)
        subStr = dg[0:16]
        m.update(subStr)
        dg = m.hexdigest()
        return dg

    def __digest(self, aValue):
        value = struct.pack("%ds" % len(aValue), aValue)
        # print value
        h = sha.new()
        h.update(value)
        dg = h.hexdigest()
        return dg

    def tradeCall(self, path, params=''):
        try:
            SHA_secret = self.__digest(self.mysecret)
            sign = self.__hmacSign(params, SHA_secret)
            reqTime = (int)(time.time() * 1000)
            params += '&sign=%s&reqTime=%d' % (sign, reqTime)
            url = ''.join(['https://trade.chbtc.com/api/', path, '?', params])
            request = urllib2.Request(url)
            response = urllib2.urlopen(request, timeout=10)
            doc = json.loads(response.read())
            return doc
        except Exception, ex:
            logging.error('chbtc request ex: %s' % str(ex))
            return None

    def apiCall(self, path, params):
        try:
            url = 'http://api.chbtc.com/data/' + path
            if params:
                url = ''.join([url, '?', params])
            request = urllib2.Request(url)
            response = urllib2.urlopen(request, timeout=10)
            doc = json.loads(response.read())
            return doc
        except Exception, ex:
            logging.error('chbtc request ex: %s' % str(ex))
            return None

    def queryAccount(self):
        try:
            params = "method=getAccountInfo&accesskey=" + self.mykey
            path = 'getAccountInfo'

            obj = self.tradeCall(path, params)
            #print obj
            return obj
        except Exception, ex:
            logging.error('chbtc queryAccount exception, %s' % str(ex))
            return None

    def syncBalance(self):
        ac = self.queryAccount()
        balance = ac['result']['balance']
        self.cny = balance['CNY']['amount']
        self.eth = balance['ETH']['amount']

    def get5mink(self):
        data = 'needTickers=1&symbol=chbtcethcny&type=5min&since=%d' % (int(time.time()) * 1000)

        req = urllib2.Request('https://trans.chbtc.com/markets/klineData')
        req.add_header('Accept', 'application/json, text/javascript, */*; q=0.01')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded; charset=UTF-8')
        req.add_header('Content-Length', 62)
        req.add_header('Referer', 'https://trans.chbtc.com/markets/kline?symbol=chbtcethcny')
        req.add_header('X-Requested-With', 'XMLHttpRequest')
        req.add_header('Origin', 'https://trans.chbtc.com')
        # req.add_header('Accept-Encoding', 'gzip, deflate')
        req.add_header('Accept-Language', 'zh-CN,zh;q=0.8')
        req.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36')

        response = urllib2.urlopen(req, data=data)
        d = json.loads(response.read())
        kdata = d['datas']['data']
        self.last5mink = kdata[-1]
        print kdata[-1]
        return kdata[-1]

    def buy(self, price, volume):
        try:
            params = "method=order&accesskey=%s&price=%f&amount=%f&tradeType=1&currency=eth" % (self.mykey, price, volume)
            path = 'order'

            obj = self.tradeCall(path, params)
            #print obj
            return obj
        except Exception, ex:
            logging.error('chbtc queryAccount exception, %s' % str(ex))
            return None

    def buyHandledCny(self, price):
        if self.eth < 0.1:
            cny = self.handledCny
            amount = cny / price
            self.buy(price + 2.0, amount)
            logging.info('buy 1111 at: %f' % price)

    def sell(self, price, volume):
        try:
            params = "method=order&accesskey=%s&price=%f&amount=%f&tradeType=0&currency=eth" % (self.mykey, price, volume)
            path = 'order'

            obj = self.tradeCall(path, params)
            #print obj
            return obj
        except Exception, ex:
            logging.error('chbtc queryAccount exception, %s' % str(ex))
            return None

    def sellAll(self, price):
        if self.eth > 0.1:
            self.sell(price - 2.0, self.eth)
            logging.info('sell 0000 at: %f, amount: %f' % (price, self.eth))

    def getLastPrice(self):
        try:
            params = ''
            path = 'getAccountInfo'

            obj = self.tradeCall(path, params)
            #print obj
            return obj
        except Exception, ex:
            logging.error('chbtc getTick exception, %s' % str(ex))
            return None

    def check(self):
        kline = self.last5mink
        # print 'kline: ', kline
        HH = kline[2]
        HC = kline[4]
        LC = kline[4]
        LL = kline[3]
        R = max(HH - LC, HC - LL)
        R = max(R, 0.06)
        end = kline[4]
        upline = end + self.k1 * R
        downline = end - self.k2 * R
        # print 'up: %f, down: %f, HH: %f, HC: %f, LC: %f, LL: %f, R: %f' % (upline, downline, HH, HC, LC, LL, R)
        d = self.apiCall('eth/ticker', '')
        if d:
            # print d
            lastPrice = float(d['ticker']['last'])
            print 'last: %f, up: %f, down: %f' % (lastPrice, upline, downline)
            if lastPrice > upline:
                if self.eth < 0.1:
                    self.buyHandledCny(lastPrice)
                    self.syncBalance()
                    logging.info('bought 1111 eth: %f' % self.eth)
                    return

            if lastPrice < downline:
                if self.eth > 0.1:
                    eth = self.eth
                    self.sellAll(lastPrice)
                    self.syncBalance()
                    logging.info('selled 0000 eth: %f' % eth)
                    return

    def run(self):
        logging.info('start!!!')
        while True:
            try:
                if self.syncBalanceIndex == 0:
                    self.syncBalance()
                    self.get5mink()
                self.syncBalanceIndex = (self.syncBalanceIndex + 1) % 8
                self.check()

            except KeyboardInterrupt:
                sys.exit(0)
            except:
                logging.error("Unexpected error: %s" % sys.exc_info()[0])

            time.sleep(1)


if __name__ == '__main__':
    # CONF.write(open(CONFIG_FILE, "w"))
    chbtcApi().run()