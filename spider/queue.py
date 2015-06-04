#!/usr/bin/env python

import logging

from threads import Semaphore, Event, Queue
from sortedcontainers import SortedSet

class RequestQ(object):

    def __init__(self):
        self.queue = SortedSet(key=lambda _: _.rating)
        self._visited = set()
        self.write_lock = Semaphore()
        self.not_empty = Event()

    def visited(self, request):
        return request in self._visited

    def put(self, request):
        with self.write_lock:
            if not self.visited(request):
                self._visited.add(request)
                self.queue.add(request)
            self.not_empty.set()

    def qsize(self):
        return len(self.queue)

    def get(self):
        self.not_empty.wait()
        with self.write_lock:
            try:
                return self.queue.pop()
            except IndexError:
                logging.error('queue tried to pop off of empty list')
            finally:
                if self.qsize()==0:
                    self.not_empty.clear()
