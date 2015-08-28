#!/usr/bin/env python

from spider.event import Events

class Handler(Events):

    def every_response(self, request, response):
        strips = lambda _: _.replace('\n', '').replace('\t', '')
        print '-'*80
        print '{} {} {}'.format(request.method,
                                request.url,
                                strips((request.body or '')[:64]))
        print '{} {:.3f} {} {}'.format(response.code,
                                       response.rtt,
                                       ', '.join(response.cookies.keys()) or 'nil',
                                       strips(response.data[:64]))
