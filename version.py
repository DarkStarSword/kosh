#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab

import sys

def checkCrypto():
  try:
    import Crypto
  except ImportError:
    print 'ERROR: Python crypto library not found - Please install pycrypto (apt-get install python-crypto)'
    sys.exit(1)
  else:
    del Crypto

def checkUrwid(required):
  try:
    import urwid
    if required.split('.') > urwid.__version__.split('.'):
      print 'ERROR: Python urwid library TOO OLD - Version %s or later is required' % required
      sys.exit(1)
  except ImportError:
    print 'ERROR: Python urwid library not found - Please install urwid %s or later (apt-get install python-urwid)' % required
    sys.exit(1)
  else:
    del urwid
