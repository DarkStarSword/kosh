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

  ttycolours = {
      'dark red'       : '\x1b[0;31;40m',
      'red'            : '\x1b[1;31;40m',
      'dark green'     : '\x1b[0;32;40m',
      'green'          : '\x1b[1;32;40m',
      'dark yellow'    : '\x1b[0;33;40m',
      'yellow'         : '\x1b[1;33;40m',
      'dark blue'      : '\x1b[0;34;40m',
      'blue'           : '\x1b[1;34;40m',
      'magenta'        : '\x1b[0;35;40m',
      'bright magenta' : '\x1b[1;35;40m',
      'cyan'           : '\x1b[0;36;40m',
      'bright cyan'    : '\x1b[1;36;40m',
      'grey'           : '\x1b[0;37;40m',
      'white'          : '\x1b[1;37;40m',

      'reset'          : '\x1b[0;37;40m',
  }

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
      try:
        ui_tty._print(prompt, end='')
      except UnicodeDecodeError:
        ui_tty._print(prompt.encode('latin-1'), end='')
    old = ui_tty.set_cbreak(fp)
    try:
      ch = fp.read(1)
    finally:
      ui_tty.restore_cbreak(old, fp)
    if echo:
      try:
        ui_tty._print(ch)
      except UnicodeDecodeError:
        ui_tty._print(ch.encode('latin-1'))
    return ch

  def status(self, msg):
    ui_tty._print(msg)

  @staticmethod
  def confirm(prompt, default=None):
    ret = ''
    prompt = prompt + ' ' + {
        True:  '(Y,n)',
        False: '(y,N)',
        None:  '(y,n)',
        }[default] + ': '
    while ret not in ['y', 'n']:
      ret = ui_tty.read_nonbuffered(prompt).lower()
      if default is not None and ret in ['', '\n']:
        return default
    return ret == 'y'

  #--------WARNING: Unstable APIs below this line------------------------------

  @staticmethod
  def _print(msg, sep=' ', end='\n', file=None):
    #print(msg, sep=sep, end=end, file=file)
    # python 2.5 doesn't have __furure__.print_function
    # FIXME: file, sep
    if end != '\n':
      print msg+end,
    else:
      print msg

  @staticmethod
  def _ctext(colour, msg):
    return ui_tty.ttycolours[colour] + msg + ui_tty.ttycolours['reset']

  @staticmethod
  def _cprint(colour, msg, sep=' ', end='\n', file=None):
    try:
      ui_tty._print(ui_tty._ctext(colour, msg), sep=sep, end=end, file=file)
    except KeyError:
      raise
  
  @staticmethod
  def _cconfirm(colour, prompt, default=None):
    try:
      return ui_tty.confirm(ui_tty._ctext(colour, prompt), default=default)
    except KeyError:
      raise
