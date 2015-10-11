#!/usr/bin/env python

import logging
import itertools

from threads import Semaphore, Event, Queue, Done, Empty
from sortedcontainers import SortedSet
from collections import defaultdict

class Leaf(object):
    def __init__(self, link, count=0):
        self.link = link
        self.count = count

def Tree(): return Leaf(defaultdict(Tree))

class CullNode(dict):

    def __init__(self, action_count=0):
        super(CullNode, self).__init__()
        self.action_count = action_count

class RequestQ(object):
    '''
    sorts queued pages via their rating
    @see protocol.Request

    keeps track of visited pages
    '''

    def __init__(self, action_limit=64, param_key_limit=16, depth_limit=16, link_limit=8):
        self.queue = SortedSet(key=lambda _: _.rating)
        self._visited = set()
        self._cull = {}
        self.write_lock = Semaphore()
        self.not_empty = Event()
        self.action_limit = action_limit
        self.param_key_limit = param_key_limit
        self.depth_limit = depth_limit
        self._visited_tree = Tree()
        self._queued_tree = Tree()

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
        request_hash = request.__hash__()
        if request_hash in self._visited:
            return True
        self._visited.add(request_hash)
        return False

    def cull_by_action(self, request):
        endpoint_hash = request.endpoint.__hash__()
        self._cull.setdefault(endpoint_hash, CullNode())
        count = self._cull[endpoint_hash].action_count + 1
        self._cull[endpoint_hash].action_count = count
        if count > self.action_limit:
            logging.debug('culling {} with count {}'.format(request.url, count))
            return True
        return False

    def cull_by_param_keys(self, request):
        if len(request.all_params()) == 0:
            return False
        endpoint_hash = request.endpoint.__hash__()
        self._cull.setdefault(endpoint_hash, CullNode())
        for key in request.all_keys():
            key_hash = key.__hash__()
            self._cull[endpoint_hash].setdefault(key_hash, 0)
            count = self._cull[endpoint_hash][key_hash] + 1
            self._cull[endpoint_hash][key_hash] = count
            if count <= self.param_key_limit:
                return False
            else:
                logging.debug('culling candidate {} with {} {} keys'.format(request.url, count, key))
        logging.debug('culling {}'.format(request.url))
        return True

    def put(self, request):
        with self.write_lock:
            if not self.visited(request):
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
