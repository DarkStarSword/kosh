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

def async(func):
  def wrap(*args, **kwargs):
    import threading
    return threading.Thread(target=func, args=args, kwargs=kwargs).start()
  return wrap

# http://www.python.org/dev/peps/pep-0318/
# From Shane Hathaway on python-dev
def singleton(cls):
  instances = {}
  def getinstance():
    if cls not in instances:
      instances[cls] = cls()
    return instances[cls]
  return getinstance

def handleErr(callback, ignoreKeyboardInterrupt = True):
  """
  Function decorator to wrap the function call within a try clause.
  If an error is caught the traceback will be passed to the callback function.
  """
  def wrap1(f):
    def wrap2(*args):
      try: f(*args)
      except:
        import traceback, sys
        if ignoreKeyboardInterrupt and sys.exc_info()[0] == KeyboardInterrupt:
          return
        callback(traceback.format_exc())
    return wrap2
  return wrap1
