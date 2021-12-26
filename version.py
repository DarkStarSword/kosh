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
import subprocess
import site

__version__ = 'v0.1 development' #FIXME: use git describe if from git repository

def import_ask_install(module, package, msg):
  try:
      return __import__(module)
  except ImportError:
      print(msg)
      answer = None
      while answer not in ('y', 'n'):
        answer = raw_input('Install %s with pip? (y/n) ' % package).lower()
      if answer == 'y':
        subprocess.call([sys.executable] + "-m ensurepip --user".split())
        subprocess.call([sys.executable, "-m", "pip", "install", package, "--user"])
        reload(site) # Ensure site-packages paths are up to date if pip just created it
        return __import__(module)

def checkCrypto():
  if not import_ask_install('Crypto', 'pycrypto', 'ERROR: Python crypto library not found'):
    sys.exit(1)

def checkUrwid(required):
  if not import_ask_install('urwid', 'urwid', 'ERROR: Python urwid library not found'):
    sys.exit(1)
  import urwid
  if required.split('.') > urwid.__version__.split('.'):
    print('ERROR: Python urwid library TOO OLD - Version %s or later is required' % required)
    sys.exit(1)
