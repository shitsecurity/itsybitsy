#!/usr/bin/env python

import logging
import itertools

from threads import Semaphore, Event, Queue, Done, Empty
from sortedcontainers import SortedSet
from collections import defaultdict

class Leaf(defaultdict):
    def __init__(self, factory, count=0):
        super(Leaf, self).__init__(factory)
        self.count = count
        self.name = None

    def visit(self, path): # TODO: rate & visit so only one traversal of tree
        for node in self.traverse(path):
            node.count += 1

    def traverse(self, path):
        tree = self
        for node in filter(None, path.split('/')):
            tree = tree[node]
            yield tree

    def __missing__(self, key):
        node = super(Leaf, self).__missing__(key)
        node.name = key
        return node

    def rate(self, path):
        ratings_all = []
        ratings_path = []
        prev = self
        for node in self.traverse(path):
            ratings_path.append(node.count)
            ratings_all.append(0)
            for element in prev.itervalues():
                ratings_all[-1] += element.count
            prev = node
        ratings = map(lambda (p,a): float(p)/(a or 1), zip(ratings_path, ratings_all))
        return 1 - sum(ratings)/float(len(ratings) or 1)

def Tree(): return Leaf(Tree)

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
                inverse_frequency_rating = self._visited_tree.rate(request.endpoint)
                logging.debug('{} inverse frequency rating for {}'.format(inverse_frequency_rating, request))
                request.rating += inverse_frequency_rating
                self._visited_tree.visit(request.endpoint)
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
