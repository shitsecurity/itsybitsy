#!/usr/bin/env python

import logging
import inspect

class Events(object):
    '''
    @see agent.Agent

    thread safety required, called by workers
    '''

    def every_link(self, link):
        '''
        extracted
        '''

    def every_form(self, form):
        '''
        extracted
        '''

    def every_request(self, request):
        '''
        pre request
        '''

    def every_response(self, request, response):
        '''
        post request
        '''

    def every_html(self, url, data, xml):
        '''
        text/html
        '''

    def every_param(self, request, key, value, method):
        '''
        param hook
        '''

class Manager(dict):

    def __init__(self):
        self.hooks = [_[0] for _ in inspect.getmembers(Events) if not _[0].startswith('_')]
    
    def _run_hooks(self, key, *args, **kwargs):
        for hook in self.get(key, []):
            hook(*args, **kwargs)

    def __getattr__(self, name):
        if name in self.hooks:
            return lambda *args, **kwargs: self._run_hooks(name, *args, **kwargs)
        else:
            raise AttributeError()

    def register(self, handler):
        for hook in self.hooks:
            if getattr(handler.__class__, hook) != getattr(Events, hook):
                self.setdefault(hook, []).append(getattr(handler, hook))

class SkipRequest(Exception):
    '''
    '''
