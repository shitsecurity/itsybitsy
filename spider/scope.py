#!/usr/bin/env python

import re
import socket
import ipaddr
import dns.name
import urlparse

from functools import wraps

class Entry(object):

    def __init__(self, ip=None, network=None, domain=None, port=None, scheme=None, query_path_re=None, domain_re=None):

        self.ip = ip

        if network is not None: network = ipaddr.IPNetwork(network)
        self.network = network

        if domain is not None:
            if domain.startswith('*.'):
                self.wildcard = True
                domain = domain[2:]
            else:
                self.wildcard = False
            domain = dns.name.from_text(str(domain))
        self.domain = domain

        self.port = port

        if scheme is not None: scheme = str(scheme).lower()
        self.scheme = scheme

        if query_path_re is not None: query_path_re = re.compile(query_path_re, re.I)
        self.query_path_re = query_path_re

        if domain_re is not None: domain_re = re.compile(domain_re, re.I)
        self.domain_re = domain_re

    def validate(self, url):
        url = urlparse.urlparse(url)

        if self.scheme is not None:
            if self.scheme != url.scheme.lower():
                return False

        if self.domain is not None:
            domain = dns.name.from_text(url.hostname)
            if self.wildcard:
                if not domain.is_subdomain(self.domain) or self.domain == domain:
                    return False
            else:
                if self.domain != domain:
                    return False

        if self.port is not None:
            if self.port != (url.port or 80):
                return False

        if self.domain_re is not None:
            if not self.domain_re.search(url.hostname):
                return False

        if self.query_path_re is not None:
            if not (self.query_path_re.search('{}?{}'.format(url.path, url.query))):
                return False

        if self.ip is not None:
            if self.ip != socket.gethostbyname(url.hostname):
                return False

        if self.network is not None:
            if ipaddr.IPAddress(socket.gethostbyname(url.hostname)) not in self.network:
                return False

        return True

class ACL(object):

    def __init__(self):
        self.entries = []

    def add(self, **kwargs):
        self.entries.append(Entry(**kwargs))

    def __call__(self, url):
        if not url.startswith('http'):
            url = 'http://{}'.format(url)
        for entry in self.entries:
            if(entry.validate(url)):
                return True
        return False

class Scope(object):

    def __init__(self, allow=ACL(), reject=ACL()):
        self.allow = allow
        self.reject = reject
