#!/usr/bin/env python

import httplib2
import logging
import urllib
import mmh3

from urlparse import urlparse
from functools import wraps
from itertools import chain

import threads

class Response(object):

    def __init__(self, headers, data):
        self.headers = headers
        try:
            encoding = headers['content-type'].split(';')[1].split('=')[-1]
        except IndexError, KeyError:
            encoding = None
        self.data = data
        if encoding:
            try:
                self.data = self.data.decode(encoding)
            except LookupError:
                logging.warning('unknown encoding {} for {}'.format(encoding, headers.get['content-location']))

    @classmethod
    def create(cls, f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            return cls(*f(*args, **kwargs))
        return wrapper

class Session(object):

    def __init__(self, ua=None, timeout=10, poolsize=16):
        self.pool = [httplib2.Http(timeout=timeout,
                                   disable_ssl_certificate_validation=True) for _ in xrange(poolsize)]
        self.headers = {'User-Agent': ua or 'Mozilla/5.0'}

        self.poolsize = poolsize
        self.pool_ii = 0
        self.pool_mutex = threads.Semaphore()

    def atomic_pool_ii(self):
        with self.pool_mutex:
            self.pool_ii = (self.pool_ii +1) % self.poolsize
            return self.pool_ii

    @property
    def connection(self):
        return self.pool[ self.atomic_pool_ii() ]

    @Response.create
    def get(self, url):
        headers, data = self.connection.request(url, 'GET', headers=self.headers)
        return headers, data

    @Response.create
    def post(self, url, data=''):
        headers, data = self.connection.request(url, 'POST', body=data, headers=self.headers)
        return headers, data

class Request(object): 
    # XXX: limit unique values per key
    # XXX: limit fuzzy diff copies per folder

    def __init__(self, url, rating=0):
        url = urlparse(url)
        self.resource = url.netloc
        self.endpoint = '{}/{}'.format(url.netloc, url.path.lstrip('/'))
        self.rating = rating # XXX: compute link rating

    @staticmethod
    def _parse_kv(kv):
        kv=kv.split('=',1)
        if len(kv)==2:
            return kv[0], kv[1]
        else:
            return kv[0], ''

    @classmethod
    def _parse_query(cls, query):
        return dict(filter(lambda (k,v): k!='', map(cls._parse_kv, query.lstrip('?').split('&'))))

    @staticmethod
    def _make_query(*args):
        return '&'.join([ '{}={}'.format(k,v) for (k,v) in chain(*args) ])

class Form(Request):

    def __init__(self, url, body='', urlencode=True):
        self.url = url
        self.params = self._parse_query(urlparse(url).query)
        self.body = body
        self.form = self._parse_query(body)
        self.urlencode = urlencode
        super(Form, self).__init__(url=url)

    def __hash__(self):
        return mmh3.hash('{}?{}'.format(self.endpoint, self._make_query(self.params.iteritems(),
                                                                        self.form.iteritems())))

    def __eq__(self, other):
        return self.params == other.params and self.form == other.form

    def __repr__(self):
        return '<{} {}>'.format(self.url, self.body[:64])

    @property
    def data(self):
        data = self.body
        if self.urlencode:
            data = urllib.quote(data)
        return data

    def invoke(self, protocol):
        return protocol.post(self.url, data=self.data)

class Link(Request):

    def __init__(self, url, parent=None):
        self.url = url
        self.params = self._parse_query(urlparse(url).query)
        super(Link, self).__init__(url=url)

    def __hash__(self):
        return mmh3.hash('{}?{}'.format(self.endpoint, self._make_query(self.params.iteritems())))

    def __eq__(self, other):
        return self.params == other.params

    def __repr__(self):
        return '<{}>'.format(self.url) 

    def invoke(self, protocol):
        return protocol.get(self.url)
