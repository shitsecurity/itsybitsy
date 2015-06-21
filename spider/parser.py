#!/usr/bin/env python

import urlparse
import lxml.html

class HTML(object):

    def parse_html(self, data):
        return lxml.html.fromstring(data)

class URL(object):

    def __init__(self, url):
        self.url = urlparse.urlparse(url)

    def normalize(self, link):
        return urlparse.urljoin(self.url.geturl(), link).replace('../','')
