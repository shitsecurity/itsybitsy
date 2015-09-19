#!/usr/bin/env python

import threads
import scope
import queue
import protocol
import agent
import trigger
import logging
import traceback
import urlparse
import socket
import event

class Spider(object):

    def __init__(self, url, workers=3, cookies=False, robots=True, sitemap=True, agent=agent.HTML):
        if not url.startswith('http'):
            url = 'http://{}'.format(url)
        self.start_url = url
        self.scope = scope.Scope()
        self.requestq = queue.RequestQ()
        self.jobq = queue.Queue()
        self.protocol = protocol.Session(cookies=cookies)
        self.pool = threads.Pool(workers)
        self.context = trigger.Context(self.jobq)
        self.events = event.Manager()
        self.free_worker = threads.Event()
        self.agent = agent
        self._crawl_robots = robots
        self._crawl_sitemap = sitemap

    def _spawn_agent(self, agent):
        return agent(self.protocol, self.requestq, self.events, self.free_worker, self.context)

    def crawl(self):
        if self._crawl_robots:
            robots = self._spawn_agent(agent.Robots)
        if self._crawl_sitemap:
            sitemap = self._spawn_agent(agent.Sitemap)
        self._spawn_agent(self.agent)

        self.requestq.put(protocol.Link(self.start_url))
        self.free_worker.set()
        while True:
            try:
                self._wait_for_free_worker()
                request = self.requestq.get()
                if not self.scope.allow(request.url) or self.scope.reject(request.url):
                    logging.info('not in scope {}'.format(request.url))
                    continue
                logging.debug('crawling {}'.format(request.url))
                self.context.url(request)
                while self.jobq.qsize()>0:
                    job = self.jobq.get()
                    self._run_job(job.action, *job.args, **job.kwargs)
            except threads.Done: # XXX gevent.hub.LoopExit
                logging.info('done crawling {}'.format(self.start_url))
                break

    def _wait_for_free_worker(self):
        if self.pool.free_count()==0:
            self.free_worker.clear()
        self.free_worker.wait()

    def _run_job(self, *args, **kwargs):
        self.pool.spawn(*args, **kwargs)

    @staticmethod
    def domain(url, **options):
        '''
        scope: domain

        @return Spider instance
        '''
        spider = Spider(url=url, **options)
        spider.scope.allow.add(domain=urlparse.urlparse(spider.start_url).hostname)
        return spider

    @staticmethod
    def site(url, **options):
        '''
        scope: domain & subdomains

        @return Spider instance
        '''
        spider = Spider(url=url, **options)
        domain = urlparse.urlparse(spider.start_url).hostname
        spider.scope.allow.add(domain=domain)
        spider.scope.allow.add(domain='*.{}'.format(domain))
        return spider

    @staticmethod
    def host(url, **options):
        '''
        scope: box

        @return Spider instance
        '''
        spider = Spider(url=url, **options)
        spider.scope.allow.add(ip=socket.gethostbyname(urlparse.urlparse(spider.start_url).hostname))
        return spider
