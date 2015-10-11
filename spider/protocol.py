#!/usr/bin/env python

import httplib2
import logging
import urllib
import time
import mmh3
import re

from urlparse import urlparse
from datetime import datetime
from functools import wraps
from itertools import chain, cycle

from sortedcontainers import SortedListWithKey

import inspect
import threads
import traceback
import tldextract

import dns.name

from queue import Queue, Empty

tldextract = tldextract.TLDExtract(suffix_list_url=False)

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
        self.domain = domain or self.origin
        self.path = path
        self.httponly = httponly
        self.secure = secure
        self.extra = kwargs
        self.created = datetime.now()

    def __repr__(self):
        return '<Cookie {}={} @{} secure={}>'.format(self.name, self.value, self.domain, self.secure)

class Cookies(list):

    '''
    parse html like email they said. concatenate duplicate headers with commas they said.
    rfc822. it is incompatible with http.
    '''

    def __init__(self, url, cookies):
        if url is not None and cookies.strip() != '':
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

            restricted_properties = ['name', 'value', 'origin']
            all_properties = [_[0] for _ in inspect.getmembers(Cookie) if not _[0].startswith('_')]
            allowed_properties = [ _ for _ in all_properties if _ not in restricted_properties ]

            super(Cookies, self).__init__()

            origin = urlparse(url).netloc
            for properties in cookies:
                name = properties[0][0]
                value = properties[0][1]
                options = dict(filter(lambda _: _[0] in allowed_properties,
                                      map(lambda (k,v): (k.lower(),v),
                                          map(lambda _: (_[0], _[1]) if len(_)==2 else (_[0], True),
                                              properties[1:]))))
                domain = options.setdefault('domain', origin)
                if dns.name.from_text(origin).is_superdomain(dns.name.from_text(domain)):
                    self.append(Cookie(name=name, value=value, origin=origin, **options))
                else:
                    logging.warning('rejected cookie {}={} for {} from {}'.format(name, value, domain, url))

    def __repr__(self):
        return ', '.join([_.name for _ in self])

class Response(object):

    def __init__(self, headers, data, request=None, rtt=0.0):
        self.code = headers.status if headers else 0
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

        self.cookies = Cookies(self.url, self.headers.get('set-cookie', ''))

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

class CookieJar(dict):

    def __init__(self, *args, **kwargs):
        super(CookieJar, self).__init__(*args, **kwargs)
        self.mutex = threads.Semaphore()
    
    @staticmethod
    def format_http_header(cookies):
        return '; '.join(['{}={}'.format(_.name, _.value) for _ in cookies])

    def get_cookies_by_url(self, url):
        url = urlparse(url)
        secure = True if url.scheme == 'https' else False
        return self.get_cookies_by_properties(domain=url.hostname, path=url.path, secure=secure)

    def _get_cookies(self, domain):
        return [v[-1] for (k,v) in self.get(domain, {}).iteritems() if len(v) > 0]

    def get_cookies_by_properties(self, domain, path='/', secure=False):
        tld = tldextract(domain).registered_domain
        return filter(lambda _: path.replace('..', '') \
                                    .replace('//', '/') \
                                    .startswith(_.path) \
                                and not (not secure and _.secure),
                      chain(self._get_cookies(domain),
                            self._get_cookies('.{}'.format(domain)),
                            self._get_cookies('.{}'.format(tld)) if tld != domain else []))

    def set_cookies(self, cookies):
        with self.mutex:
            for cookie in cookies:
                self._set_cookie(cookie)

    def set_cookie(self, cookie):
        with self.mutex:
            self._set_cookie(cookie)

    def _set_cookie(self, cookie):
        self.setdefault(cookie.domain, {}) \
            .setdefault(cookie.name, SortedListWithKey(key=lambda _: _.created)) \
            .add(cookie)

class Session(object):

    def __init__(self, ua=None, timeout=10, cookies=False):
        self.pool = Queue()
        self.timeout = timeout
        self.headers = {'User-Agent': ua or 'Mozilla/5.0'}
        self.cookies = cookies
        self.cookiejar = CookieJar()

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

    def _cookie_header(self, url):
        return self.cookiejar.format_http_header(chain(self.headers.get('Cookie', []),
                                                       self.cookiejar.get_cookies_by_url(url)))

    def get(self, url, method='GET'):
        with self.connection as connection:
            try:
                start = time.time()
                headers = dict(self.headers, Cookie=self._cookie_header(url)) if self.cookies else self.headers
                headers, data = connection.request(url, method, headers=headers)
                rtt = time.time() - start
                response = Response(headers, data, ResponseRequest(url, method=method), rtt)
                self.cookiejar.set_cookies(response.cookies)
            except:
                logging.error('timeout {} {}\n{}'.format(method, url, traceback.format_exc()))
                response = Response({}, '')
            finally:
                return response

    def post(self, url, data='', method='POST'):
        with self.connection as connection:
            try:
                start = time.time()
                headers = dict(self.headers, Cookie=self._cookie_header(url)) if self.cookies else self.headers
                headers, data = connection.request(url, method, body=data, headers=headers)
                rtt = time.time() - start
                response = Response(headers, data, ResponseRequest(url, data, method=method), rtt)
                self.cookiejar.set_cookies(response.cookies)
            except:
                logging.error('timeout {} {}\n{}'.format(method, url, traceback.format_exc()))
                response = Response({}, '')
            finally:
                return response

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

    def set_param(self, key, value, method='GET'):
        if method.upper() == 'GET':
            self.params[key] = value
        elif self.body is not None:
            self.form[key] = value

    def get_param(self, key, method='GET'):
        if method.upper() == 'GET':
            return self.params.get(key)
        elif self.body is not None:
            return self.form.get(key)

class Form(Request):

    def __init__(self, url, body='', urlencode=True):
        self.url = url
        self.params = self._parse_query(urlparse(url).query)
        self.form = self._parse_query(body)
        self.urlencode = urlencode
        self.method = 'POST'
        super(Form, self).__init__(url=url)

    def __hash__(self):
        return self._make_hash(self.params.iteritems(), self.form.iteritems())

    def __eq__(self, other):
        return self.params == other.params and self.form == other.form

    def __repr__(self):
        return '<{} {}>'.format(self.url, self._make_body()[:64])

    def _make_body(self):
        if len(self.form.items())==1 and self.form.values()[0] == '':
            return self.form.keys()[0]
        return '&'.join(['{}={}'.format(k,v) for (k,v) in self.form.iteritems()])

    @property
    def body(self):
        return self._make_body()

    @property
    def data(self):
        data = self._make_body()
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

    def all_keys_with_method(self):
        return list(chain(zip(self.params.keys(), cycle(['GET'])),
                          zip(self.form.keys(), cycle([self.method]))))

    def all_values_with_method(self):
        return list(chain(zip(self.params.values(), cycle(['GET'])),
                          zip(self.form.values(), cycle([self.method]))))

    def all_params_with_method(self):
        return list(chain(zip(self.params.items(), cycle(['GET'])),
                          zip(self.form.items(), cycle([self.method]))))

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
        return self.params.keys()

    def all_values(self):
        return self.params.values()

    def all_params(self):
        return self.params.items()

    def all_keys_with_method(self):
        return zip(self.params.keys()(), cycle([self.method]))

    def all_values_with_method(self):
        return zip(self.params.values(), cycle([self.method]))

    def all_params_with_method(self):
        return zip(self.params.items(), cycle([self.method]))
