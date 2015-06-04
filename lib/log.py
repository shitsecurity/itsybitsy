#!/usr/bin/env python

import logging

def log( level=logging.DEBUG ):
    format='%(levelname)8s [*] %(message)s'
    logging.basicConfig(level=level,format=format)
