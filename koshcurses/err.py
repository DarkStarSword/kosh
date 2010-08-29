#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab

def showErr(msg):
  try:
    import urwid
    lb = urwid.ListBox(
        urwid.SimpleListWalker([ urwid.Text(msg) ]))

    def exit_on_q(input):
      if input.lower() in ('enter', 'q', 'esc'):
        raise urwid.ExitMainLoop()
    urwid.MainLoop(lb, unhandled_input = exit_on_q).run()
  finally:
    print msg
