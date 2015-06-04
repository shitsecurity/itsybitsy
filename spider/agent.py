#!/usr/bin/env python

import urlparse
import parser
import logging
import protocol
import trigger

class Agent(object):

    def __init__(self, protocol, scope, requestq, events, *args, **kwargs):
        self.protocol = protocol
        self.scope = scope
        self.requestq = requestq
        self.events = events
        super(Agent, self).__init__(*args, **kwargs)

class Robots(Agent, trigger.Robots):
    '''
    robots.txt
    '''
    def __call__(self, url):
        resource = urlparse.urlparse(url)
        url = '{}://{}/robots.txt'.format(resource.scheme, resource.netloc)
        self.parse(url, self.protocol.get(url).data)

    def parse(self, url, data):
        normalizer = parser.URL(url)
        lines = data.split('\n')
        for line in [_.lower() for _ in lines]:
            if line.startswith('disallow') \
            or line.startswith('allow') \
            or line.startswith('sitemap'):
                link = line.split(' ')[1].rstrip('*$?').replace('*', '')
                canonical_url = normalizer.normalize(link)
                logging.info('found {} by robots from {}'.format(canonical_url, url))
                self.url(canonical_url)
            elif line.startswith('user-agent'): pass
            else: pass

    def url(self, url):
        self.requestq.put(protocol.Link(url))

class Sitemap(Agent, parser.HTML, trigger.Sitemap):
    '''
    sitemap.xml
    '''
    def __call__(self, url):
        resource = urlparse.urlparse(url)
        url = '{}://{}/sitemap.xml'.format(resource.scheme, resource.netloc)
        self.parse(url, self.protocol.get(url).data)

    def parse(self, url, data):
        root = super(Sitemap, self).parse(data)
        for link in root.xpath('//urlset/url/loc/text()'):
            logging.info('found {} by sitemap from {}'.format(link, url))
            self.url(link)

    def url(self, url):
        self.requestq.put(protocol.Link(url))

class HTML(Agent, parser.HTML, trigger.HTML):
    '''
    html
    '''
    def __call__(self, request):
        self.parse(request.url, self.protocol.get(request.url).data) # XXX: post data

    def parse(self, url, data):
        normalizer = parser.URL(url)
        root = super(HTML, self).parse(data)
        for link in root.xpath('//a/@href'):
            canonical_url = normalizer.normalize(link)
            logging.info('found {} on {}'.format(canonical_url, url))
            self.url(canonical_url)
        # XXX: src
        # XXX: form

    def url(self, url):
        self.requestq.put(protocol.Link(url))
