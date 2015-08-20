#!/usr/bin/env python

import re
import urlparse
import lxml.html
import logging

class HTML(object):

    xml = re.compile('^\s*<\??xml version="1.0" encoding="utf-8"\??>', re.I)

    def parse_html(self, data):
        data = self.xml.sub('', data, 1) # lxml quirk
        return lxml.html.fromstring(data)

class URL(object):

    def __init__(self, url):
        self.url = urlparse.urlparse(url)

    def normalize(self, link):
        return urlparse.urljoin(self.url.geturl(), link).replace('../','').encode('utf8')
