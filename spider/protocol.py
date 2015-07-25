#!/usr/bin/env python

import itertools
import httplib2
import logging
import urllib
import mmh3
import re

from urlparse import urlparse
from functools import wraps
from itertools import chain

import threads

from queue import Queue, Empty

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

class HTTPConnection(httplib2.Http):

    def __init__(self, pool, *args, **kwargs):
        self.pool = pool
        super(HTTPConnection, self).__init__(*args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, traceback):
        self.pool.put(self)

class Session(object):

    def __init__(self, ua=None, timeout=10):
        self.pool = Queue()
        self.timeout = timeout
        self.headers = {'User-Agent': ua or 'Mozilla/5.0'}

    def _spawn_connection(self):
        return HTTPConnection(pool=self.pool,
                              timeout=self.timeout,
                              disable_ssl_certificate_validation=True)

    @property
    def connection(self):
        try:
            return self.pool.get_nowait()
        except Empty:
            return self._spawn_connection()

    @Response.create
    def get(self, url):
        with self.connection as connection:
            headers, data = connection.request(url, 'GET', headers=self.headers)
            return headers, data

    @Response.create
    def post(self, url, data=''):
        with self.connection as connection:
            headers, data = connection.request(url, 'POST', body=data, headers=self.headers)
            return headers, data

class Request(object):

    def __init__(self, url, rating=0):
        url = urlparse(url)
        self.resource = url.netloc
        self.endpoint = '{}/{}'.format(url.netloc, url.path.lstrip('/'))
        self.rating = rating
        super(Request, self).__init__()
        self.action = url.path

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
        return '&'.join(sorted([ '{}={}'.format(k,v) for (k,v) in chain(*args) ]))

    def _make_hash(self, *args):
        return mmh3.hash('{}?{}'.format(self.endpoint, self._make_query(*args)))

class Form(Request):

    def __init__(self, url, body='', urlencode=True):
        self.url = url
        self.params = self._parse_query(urlparse(url).query)
        self.body = body
        self.form = self._parse_query(body)
        self.urlencode = urlencode
        super(Form, self).__init__(url=url)
        self.rating += 1

    def __hash__(self):
        return self._make_hash(self.params.iteritems(), self.form.iteritems())

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

    def all_keys(self):
        return list(chain(self.params.keys(), self.form.keys()))

    def all_values(self):
        return list(chain(self.params.values(), self.form.keys()))

    def all_params(self):
        return list(chain(self.params.iteritems(), self.form.iteritems()))

class Link(Request):

    def __init__(self, url, parent=None):
        self.url = url
        self.params = self._parse_query(urlparse(url).query)
        super(Link, self).__init__(url=url)

    def __hash__(self):
        return self._make_hash(self.params.iteritems())

    def __eq__(self, other):
        return self.params == other.params

    def __repr__(self):
        return '<{}>'.format(self.url) 

    def invoke(self, protocol):
        return protocol.get(self.url)

    def all_keys(self):
        return list(self.params.keys())

    def all_values(self):
        return list(self.params.values())

    def all_params(self):
        return list(self.params.iteritems())
