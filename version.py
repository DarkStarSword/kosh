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
import os
import subprocess
import importlib
import site

__version__ = 'v0.1 development' #FIXME: use git describe if from git repository

HAS_TERMUX_API = False

def import_ask_install(module, package, msg, version_check=None, uninstall=None):
  try:
      ret = __import__(module)
  except ImportError:
      print(msg)
      answer = None
      while answer not in ('y', 'n'):
        answer = input('Install %s with pip? (y/n) ' % package).lower()
      if answer == 'y':
        subprocess.call([sys.executable] + "-m ensurepip --user".split())
        if uninstall:
          subprocess.call([sys.executable, "-m", "pip", "uninstall", uninstall])
        subprocess.call([sys.executable, "-m", "pip", "install", package, "--user"])
        importlib.reload(site) # Ensure site-packages paths are up to date if pip just created it
        ret = __import__(module)
  if version_check is not None and not version_check(ret):
    print('%s version too old' % module)
    answer = None
    while answer not in ('y', 'n'):
      answer = input('Upgrade %s with pip? (y/n) ' % package).lower()
      if answer == 'y':
        subprocess.call([sys.executable] + "-m ensurepip --user".split())
        if uninstall:
          subprocess.call([sys.executable, "-m", "pip", "uninstall", uninstall])
        subprocess.call([sys.executable, "-m", "pip", "install", package, "--upgrade", "--user"])
        importlib.reload(site) # Ensure site-packages paths are up to date if pip just created it
        ret = __import__(module)
  return ret

def checkCrypto():
  def version_check(module):
    return module.version_info[0] >= 3
  try:
    import Cryptodome
  except ImportError:
    if not import_ask_install('Crypto', 'pycryptodome', 'ERROR: Python crypto library not found',
        version_check=version_check, uninstall='pycrypto'):
      sys.exit(1)

def checkUrwid(required):
  if not import_ask_install('urwid', 'urwid', 'ERROR: Python urwid library not found'):
    sys.exit(1)
  import urwid
  if required.split('.') > urwid.__version__.split('.'):
    print('ERROR: Python urwid library TOO OLD - Version %s or later is required' % required)
    sys.exit(1)

def checkXClipboard():
  import_ask_install('Xlib', 'xlib', 'WARNING: Python-Xlib not installed, clipboard integration will be unavailable')

def checkTermuxAPI():
  global HAS_TERMUX_API
  HAS_TERMUX_API = not not import_ask_install('termux', 'termux-api', 'WARNING: Python Termux-API not installed, clipboard integration will be unavailable')
  # TODO: Verify termux API Android app + package are both installed

def is_wsl():
  import platform
  return 'microsoft-standard' in platform.uname().release

def checkWSLClipboard():
  import wslclipboard
  native_python_is_stub = wslclipboard.native_python_is_stub()
  if native_python_is_stub is None:
    # No python.exe, not even the stub to install it
    print('WSL detected, but native Python unavailable - clipboard implementation will be limited. Install native python and add to path to enable advanced clipboard support.\nPress enter to continue...')
    input()
  if native_python_is_stub is True:
    print('WSL detected, but native Python not installed - clipboard implementation will be limited.')
    print('If Python is already installed via the Windows store and you are still seeing this message,')
    print('open Settings ->...-> "App Execution Aliases" and try cycling the python.exe alias off and on.')
    answer = None
    while answer not in ('y', 'n'):
      answer = input('Open Windows Store to install native Python for advanced clipboard integration? (y/n) ').lower()
    if answer == 'y':
      wslclipboard.attempt_install_winstore_python()
