#!/usr/bin/env python

import logging

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
