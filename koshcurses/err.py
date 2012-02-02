#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab

def _show_err(msg):
  import urwid
  lb = urwid.ListBox(
      urwid.SimpleListWalker([ urwid.Text(msg) ]))

  def exit_on_q(input):
    if input in ['enter', 'q', 'Q', 'esc']:
      raise urwid.ExitMainLoop()
  urwid.MainLoop(lb, unhandled_input = exit_on_q).run()

def show_err(msg):
  '''
  Try to display an error with urwid. This instantiates it's own main loop, so
  will effectively be modal until it is dismissed.

  If it is unable to display the message with urwid it will print it to the
  console.
  '''
  try:
    _show_err(msg)
  except Exception, e:
    print msg
    print '-' * 79
    print 'Additionally, an %s occurred while attempting to display the error: %s' \
        % (e.__class__.__name__, str(e))
    print '-' * 79

def show_err_exit(msg):
  '''
  Try to display an error with urwid and print it to the terminal whether or
  not that succeeded.

  This doesn't exit the program, it is intended for use when a fatal error is
  being displayed and the program is going to exit.
  '''
  try:
    _show_err(msg)
  finally:
    print msg
