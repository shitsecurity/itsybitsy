#!/usr/bin/env python

import spider.threads

import argparse
import logging

from lib.log import log, SILENT
from spider.spider import Spider
from plugins import html, response

def parse_args():
    description = ''
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--verbose', dest='verbose', action='store_true', help='be verbose')
    parser.add_argument('--quiet', dest='quiet', action='store_true', help='suppress output except errors')
    parser.add_argument('--silent', dest='silent', action='store_true', help='suppress all output')
    parser.add_argument('--target', dest='target', metavar='[domain]', help='target url')
    parser.add_argument('--robots-off', dest='robots', action='store_false', help='ignore robots.txt', default=True)
    parser.add_argument('--sitemap-off', dest='sitemap', action='store_false', help='ignore sitemap.xml', default=True)
    parser.add_argument('--cookies', dest='cookies', action='store_true', help='handle cookies')
    parser.add_argument('--workers', dest='workers', metavar='[workers]', type=int, help='amount of workers', default=3)
    parser.add_argument('--plugin-html', dest='html', action='store_true', help='print html size')
    parser.add_argument('--plugin-response', dest='response', action='store_true', help='print response data')
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

    spider = Spider.site(args.target, robots=args.robots, sitemap=args.sitemap, cookies=args.cookies)
    if args.html:
        spider.events.register(html.Handler())
    if args.response:
        spider.events.register(response.Handler())
    spider.crawl()
