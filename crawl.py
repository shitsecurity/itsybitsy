#!/usr/bin/env python

import spider.threads

import argparse
import logging

from lib.log import log
from spider.spider import Spider

def parse_args():
    description = ''
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--verbose', dest='verbose', action='store_true',
                        help='be verbose')
    parser.add_argument('--target', dest='target',
                        metavar='sub.domain.tld', help='target url')
    parser.add_argument('--robots-off', dest='robots', action='store_false',
                        help='ignore robots.txt', default=True)
    parser.add_argument('--sitemap-off', dest='sitemap', action='store_false',
                        help='ignore robots.txt', default=True)
    args = parser.parse_args()
    return args

if __name__ == '__main__':
    args = parse_args()
    if args.verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    log(level=level)

    spider = Spider.site(args.target)
    spider.crawl_robots = args.robots
    spider.crawl_sitemap = args.sitemap
    spider.crawl()

    # python crawl.py --target localhost
