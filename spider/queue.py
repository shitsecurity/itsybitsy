#!/usr/bin/env python

import logging
import itertools

from threads import Semaphore, Event, Queue, Done, Empty
from sortedcontainers import SortedSet
from collections import defaultdict

def Tree(): return defaultdict(Tree)

class RequestQ(object):
    '''
    sorts queued pages via their rating
    @see protocol.Request

    keeps track of visited pages
    '''

    _action_count = {}
    _param_key_count = {}

    _link_tree = Tree()

    def __init__(self, action_limit=64, param_key_limit=16, depth_limit=10):
        self.queue = SortedSet(key=lambda _: _.rating)
        self._visited = set()
        self.write_lock = Semaphore()
        self.not_empty = Event()
        self.action_limit = action_limit
        self.param_key_limit = param_key_limit
        self.depth_limit = depth_limit

    def visited(self, request):
        if(any([ _(request) for _ in [ self.cull_by_hash,
                                       self.cull_by_depth,
                                       self.cull_by_action,
                                       self.cull_by_param_keys ]])):
            return True
        return False

    def cull_by_depth(self, request):
        if len(request.action.split('/')) > self.depth_limit:
            return True
        return False

    def cull_by_hash(self, request):
        if request in self._visited:
            return True
        return False

    def cull_by_action(self, request):
        self._action_count.setdefault(request.endpoint, 0)
        self._action_count[request.endpoint] += 1
        count = self._action_count[request.endpoint]
        if count > self.action_limit:
            logging.debug('culling {} with count {}'.format(request.url, count))
            return True
        return False

    def cull_by_param_keys(self, request):
        if len(request.all_params()) == 0:
            return False
        self._param_key_count.setdefault(request.endpoint, {})
        for key in request.all_keys():
            self._param_key_count[request.endpoint].setdefault(key, 0)
            self._param_key_count[request.endpoint][key] += 1
            count = self._param_key_count[request.endpoint][key]
            if count <= self.param_key_limit:
                return False
            else:
                logging.debug('culling candidate {} with {} {} keys'.format(request.url, count, key))
        logging.debug('culling {}'.format(request.url))
        return True

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
                raise Done()
            finally:
                if self.qsize()==0:
                    self.not_empty.clear()
