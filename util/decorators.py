#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab

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

def handleErr(callback):
  """
  Function decorator to wrap the function call within a try clause.
  If an error is caught the traceback will be passed to the callback function.
  """
  def wrap1(f):
    def wrap2(*args):
      try: f(*args)
      except:
        import traceback
        callback(traceback.format_exc())
    return wrap2
  return wrap1
