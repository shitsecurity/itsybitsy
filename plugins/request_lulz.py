#!/usr/bin/env python

from spider.event import Events

class Handler(Events):

    def every_param(self, request, key, value, method):
        request.set_param(key, 'lulz', method)
        print '{} {}={}'.format(method, key, request.get_param(key, method))
