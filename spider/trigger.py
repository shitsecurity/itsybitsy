#!/usr/bin/env python

import urlparse
import threads

from collections import namedtuple
Job = namedtuple('Job', ['action','args','kwargs'])

class Context(object):

    def __init__(self, jobq=threads.Queue()):
        self.resources = []
        self.mutex = threads.Semaphore()
        self.subscribers = {}
        self.jobq = jobq
    
    def url(self, request):
        url = urlparse.urlparse(request.url)
        notify = False
        with self.mutex:
            if url.netloc not in self.resources:
                self.resources.append(url.netloc)
                notify = True
        if notify: self.notify('new.resource', request.url)
        self.notify('new.request', request)

    def notify(self, key, *args, **kwargs):
        for subscriber in self.subscribers.get(key, []):
            self.jobq.put(Job(action=subscriber, args=args, kwargs=kwargs))

    def subscribe(self, key, subscriber):
        self.subscribers.setdefault(key, []).append(subscriber)

class Trigger(object):

    def __init__(self, context=Context()):
        self.context = context

class Robots(Trigger):

    def __init__(self, *args, **kwargs):
        super(Robots, self).__init__(*args, **kwargs)
        self.context.subscribe('new.resource', self)

class Sitemap(Trigger):

    def __init__(self, *args, **kwargs):
        super(Sitemap, self).__init__(*args, **kwargs)
        self.context.subscribe('new.resource', self)

class HTML(Trigger):

    def __init__(self, *args, **kwargs):
        super(HTML, self).__init__(*args, **kwargs)
        self.context.subscribe('new.request', self)
