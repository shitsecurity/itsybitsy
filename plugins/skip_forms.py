#!/usr/bin/env python

from spider.event import Events, SkipRequest

class Handler(Events):

    def every_request(self, request):
        if request.method == 'POST':
            raise SkipRequest()
