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

def normalize_query(query):
    return '?{}'.format(query.encode('utf8')) if query != '' else query

class URL(object):

    def __init__(self, url):
        self.url = urlparse.urlparse(url)

    def normalize(self, link):
        url = urlparse.urlparse(urlparse.urljoin(self.url.geturl(), link))
        return '{}://{}/{}{}'.format(*[_.encode('utf8') 
                                       for _ in [url.scheme,
                                                 url.netloc,
                                                 url.path.lstrip('/') \
                                                         .replace('..', '') \
                                                         .replace('//', '/'),
                                                 normalize_query(url.query).encode('utf8')]])
