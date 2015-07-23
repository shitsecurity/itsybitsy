#!/usr/bin/env python

import spider.threads

import argparse
import logging

from lib.log import log, SILENT
from spider.spider import Spider
from plugins import events

def parse_args():
    description = ''
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--verbose', dest='verbose', action='store_true',
                        help='be verbose')
    parser.add_argument('--quiet', dest='quiet', action='store_true',
                        help='suppress output except errors')
    parser.add_argument('--silent', dest='silent', action='store_true',
                        help='suppress all output')
    parser.add_argument('--target', dest='target',
                        metavar='domain', help='target url')
    parser.add_argument('--robots-off', dest='robots', action='store_false',
                        help='ignore robots.txt', default=True)
    parser.add_argument('--sitemap-off', dest='sitemap', action='store_false',
                        help='ignore sitemap.xml', default=True)
    parser.add_argument('--events', dest='events', action='store_true',
                        help='handle events')
    args = parser.parse_args()

    if len(filter(lambda _: _==True,[args.verbose, args.quiet, args.silent])) > 1:
        parser.error('invalid verbosity')

    return args

if __name__ == '__main__':
    args = parse_args()
    if args.verbose:
        level = logging.DEBUG
    elif args.quiet:
        level = logging.WARN
    elif args.silent:
        level = SILENT
    else:
        level = logging.INFO
    log(level=level)

    spider = Spider.site(args.target)
    spider.crawl_robots = args.robots
    spider.crawl_sitemap = args.sitemap
    if args.events:
        spider.events = events.Handler()
    spider.crawl()
