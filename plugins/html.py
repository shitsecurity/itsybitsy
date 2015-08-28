#!/usr/bin/env python

from spider.event import Events

class Handler(Events):

    def every_html(self, url, data, html):
        print '{:.0f}kb {}'.format(len(data)/1024.0, url)
