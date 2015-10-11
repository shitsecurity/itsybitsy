#!/usr/bin/env python

import re
import urlparse
import parser
import logging
import protocol
import trigger

class Agent(object):
    '''
    @param protocol - fetch resources
    @see protocol.Session

    @param requestq - queue up found resources
    @see queue.ReuqestQ

    @param events - trigger callback events
    @see event.Events

    @param free_worker - set() when worker is done for sync w/ Spider.crawl
    blocks spider from prematurely popping requests off of RequestQ
    @see threads.Event
    @see spider.Spider
    @see queue.RequestQ
    '''

    def __init__(self, protocol, requestq, events, free_worker, *args, **kwargs):
        self.protocol = protocol
        self.requestq = requestq
        self.events = events
        self.free_worker = free_worker
        super(Agent, self).__init__(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        self.action(*args, **kwargs)
        self.free_worker.set()

class Robots(Agent, trigger.Robots):
    '''
    robots.txt
    '''
    def action(self, url):
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
        link = protocol.Link(url)
        self.events.every_link(link)
        self.requestq.put(link)

class Sitemap(Agent, parser.HTML, trigger.Sitemap):
    '''
    sitemap.xml
    '''
    def action(self, url):
        resource = urlparse.urlparse(url)
        url = '{}://{}/sitemap.xml'.format(resource.scheme, resource.netloc)
        self.parse(url, self.protocol.get(url).data)

    def parse(self, url, data):
        root = super(Sitemap, self).parse_html(data)
        for link in root.xpath('//urlset/url/loc/text()'):
            logging.info('found {} by sitemap from {}'.format(link, url))
            self.url(link)

    def url(self, url):
        link = protocol.Link(url)
        self.events.every_link(link)
        self.requestq.put(link)

class HTML(Agent, parser.HTML, trigger.HTML):
    '''
    html
    '''
    def action(self, request):
        for ((k,v),method) in request.all_params_with_method():
            self.events.every_param(request, k, v, method)
        self.events.every_request(request)
        response = request.invoke(self.protocol)
        self.events.every_response(request, response)
        if self.is_html(response):
            self.parse_html(request.url, response.data)
        else:
            logging.warn('unknown content-type {} {}'.format(response.headers.get('content-type'), response.url))

    def is_html(self, response):
        header = response.headers.get('content-type')
        if header is None: return False
        type = header.split(' ')[0].rstrip(';')
        if type.lower() == 'text/html':
            return True
        return False

    def parse_html(self, url, data):
        normalizer = parser.URL(url)
        if data.strip() == '':
            return
        root = super(HTML, self).parse_html(data)
        self.events.every_html(url, data, root)
        for link in root.xpath('//a/@href'):
            canonical_url = normalizer.normalize(link)
            logging.info('found {} on {}'.format(canonical_url, url))
            self.link(canonical_url)
        for link in root.xpath('//@src'):
            canonical_url = normalizer.normalize(link)
            logging.info('found {} on {}'.format(canonical_url, url))
            self.link(canonical_url)
        for form in root.xpath('//form'):
            method = form.get('method','GET')
            action = form.get('action','/')
            canonical_url = normalizer.normalize(action)
            query = []
            for input in form.xpath('//input'):
                name = input.get('name', '')
                value = input.get('value', '')
                if name is not None:
                    query.append('{}={}'.format(name.encode('utf8'), value.encode('utf8')))
                else:
                    query.append('{}'.format(name.encode('utf8')))
                    logging.warn('anonymous input on {}'.format(url))
            query_str = '&'.join(query)
            if action == 'GET':
                self.form(url + '?' + query_str)
            else:
                self.form(url, body=query_str)

    def link(self, url):
        link = protocol.Link(url)
        self.events.every_link(link)
        self.requestq.put(link)

    def form(self, url, body=''):
        form = protocol.Form(url, body=body)
        self.events.every_form(form)
        self.requestq.put(form)
