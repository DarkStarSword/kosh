#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab

import ui_null
import sys, tty

class ui_tty(object):
  # We don't implement a mainloop, but allow it to be queried, always returning
  # None for any query for easy compatibility with any code that implements
  # their own event loop and queries the mainloop (typically to get
  # file descriptors that need to be queries and input relayed):
  mainloop = ui_null.ui_null()

  # I want to be able to call these without instantiating this class for the moment:
  @staticmethod
  def set_cbreak(fp=sys.stdin):
    old = None
    try:
      fileno = fp.fileno()
      old = tty.tcgetattr(fileno)
      tty.setcbreak(fileno)
    except: pass
    return old

  @staticmethod
  def restore_cbreak(old, fp=sys.stdin):
    if old is None: return
    fileno = fp.fileno()
    tty.tcsetattr(fileno, tty.TCSADRAIN, old)

  @staticmethod
  def read_nonbuffered(prompt=None, echo=True, size=1, fp=sys.stdin):
    """
    Read size bytes from this file, which must be a tty (typically stdin),
    optionally displaying a prompt.
    """
    fileno = fp.fileno()
    if prompt:
      print prompt,
    old = ui_tty.set_cbreak(fp)
    try:
      ch = fp.read(1)
    finally:
      ui_tty.restore_cbreak(old, fp)
    if echo:
      print(ch)
    return ch

  def status(self, msg):
    print msg

