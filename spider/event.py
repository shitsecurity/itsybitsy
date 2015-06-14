#!/usr/bin/env python

import logging

class Events(object):
    '''
    @see agent.Agent

    thread safety required, called by workers
    '''

    def every_url(self, entity):
        '''
        extracted
        '''

    def every_link(self, url):
        '''
        @see every_url
        '''

    def every_form(self, form):
        '''
        @see every_url
        '''

    def every_request(self, request):
        '''
        pre request
        '''

    def every_response(self, request, response):
        '''
        post request
        '''

    def every_html(self, url):
        '''
        @see every_response
        '''
