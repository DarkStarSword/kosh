#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab

# Copyright (C) 2009-2021 Ian Munsie
#
# Kosh is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Kosh is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Kosh.  If not, see <http://www.gnu.org/licenses/>.

import sys

__version__ = 'v0.1 development' #FIXME: use git describe if from git repository

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
    print 'ERROR: Python urwid library not found - Please install urwid %s or later (python -m ensurepip; python -m pip install urwid)' % required
    sys.exit(1)
  else:
    del urwid
