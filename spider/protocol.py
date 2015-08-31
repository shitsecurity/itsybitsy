#!/usr/bin/env python

import itertools
import httplib2
import logging
import urllib
import time
import mmh3
import re

from urlparse import urlparse
from functools import wraps
from itertools import chain

import threads
import traceback

from queue import Queue, Empty

class Cookie(object):

    def __init__(self,
                 name,
                 value,
                 expires=None,
                 origin=None,
                 domain=None,
                 path='/',
                 httponly=False,
                 secure=False,
                 **kwargs):

        self.name = name
        self.value = value
        self.expires = expires
        self.origin = origin
        self.domain = domain
        self.path = path
        self.httponly = httponly
        self.secure = secure
        self.extra = kwargs

class Cookies(list):

    '''
    parse html like email they said. concatenate duplicate headers with commas they said.
    rfc822. it is incompatible with http.
    '''

    def __init__(self, cookies):
        if cookies.strip() != '':
            cookies = cookies.replace(';', '; ').replace(',', ', ')
            tokens = filter(lambda _: _!='', [_.strip() for _ in cookies.split(' ')])
            tokens[-1] = tokens[-1].rstrip(',') + ','
            cookies = []
            properties = []
            ii = 0
            while ii < len(tokens):
                token = tokens[ii]
                if not token.endswith(';') and not token.endswith(',') or token.lower().startswith('expires='):
                    for index, property in enumerate(tokens[ii+1:]):
                        if property.endswith(';') or property.endswith(','):
                            token = ' '.join(tokens[ii:ii+index+2])
                            break
                    ii += index + 1
                properties.append(token.rstrip(';,').split('=',1))
                if token.endswith(',') or ii==len(tokens)-1:
                    cookies.append(properties)
                    properties = []
                ii += 1
            super(Cookies, self).__init__([Cookie(name=property[0][0],
                                                  value=property[0][1],
                                                  **(dict(map(lambda (k,v): (k.lower(),v),
                                                              map(lambda _: (_[0], _[1]) if len(_)==2 else (_[0], True),
                                                                  property[1:]))))) for property in cookies])

    def __repr__(self):
        return ', '.join([_.name for _ in self])

class Response(object):

    def __init__(self, headers, data, request=None, rtt=0.0):
        self.code = headers.status
        self.rtt = rtt
        self.headers = headers
        try:
            encoding = headers['content-type'].split(';')[1].split('=')[-1]
        except (IndexError, KeyError):
            encoding = None

        if encoding:
            try:
                self.data = data.decode(encoding)
            except LookupError:
                logging.warning('unknown encoding {} for {}'.format(encoding, headers.get['content-location']))
        else:
            self.data = data

        self.request = request

        self.cookies = Cookies(self.headers.get('set-cookie', ''))

    @classmethod
    def create(cls, f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return cls(*f(*args, **kwargs))
            except HTTPException:
                return cls({}, '')
        return wrapper

    @property
    def url(self):
        try:
            return self.request.url
        except AttributeError:
            return None

class HTTPConnection(httplib2.Http):

    def __init__(self, pool, *args, **kwargs):
        self.pool = pool
        super(HTTPConnection, self).__init__(*args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, traceback):
        self.pool.put(self)

class ResponseRequest(object):

    def __init__(self, url, data=None, method=None):
        self.url = url
        self.data = data
        self.method = method

class HTTPException(Exception): pass

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
    def get(self, url, method='GET'):
        with self.connection as connection:
            try:
                start = time.time()
                headers, data = connection.request(url, method, headers=self.headers)
                rtt = time.time() - start
                return headers, data, ResponseRequest(url, method=method), rtt
            except:
                logging.error('timeout {} {}\n{}'.format(method, url, traceback.format_exc()))
                raise HTTPException()

    @Response.create
    def post(self, url, data='', method='POST'):
        with self.connection as connection:
            try:
                start = time.time()
                headers, data = connection.request(url, method, body=data, headers=self.headers)
                rtt = time.time() - start
                return headers, data, ResponseRequest(url, data, method=method), rtt
            except:
                logging.error('timeout {} {}\n{}'.format(method, url, traceback.format_exc()))
                raise HTTPException()

class Request(object):

    def __init__(self, url, rating=0):
        url = urlparse(url)
        self.resource = url.netloc
        self.endpoint = '{}/{}'.format(url.netloc, url.path.lstrip('/'))
        self.rating = rating
        super(Request, self).__init__()
        self.action = url.path
        self.rate()

    def rate(self):
        images = ['png', 'jpg', 'jpeg', 'gif', 'webm']
        docs = ['pdf', 'doc', 'docx']
        styles = ['js', 'css']
        ext = self.action.split('.')[-1].lower()

        if ext in images:
            self.rating += 1
        elif ext in docs:
            self.rating += 2
        elif ext in styles:
            self.rating += 3
        else:
            self.rating += 4

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
        self.method = 'POST'
        super(Form, self).__init__(url=url)

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

    def rate(self):
        super(Form, self).rate()
        self.rating += 1

class Link(Request):

    def __init__(self, url, parent=None):
        self.url = url
        self.params = self._parse_query(urlparse(url).query)
        self.method = 'GET'
        self.body = None
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
