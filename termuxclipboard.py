#!/usr/bin/env python
# vi:sw=2:ts=2:sts=2:expandtab

from ui import ui_tty, ui_null
import sys
import select
import termux

def copy_text_simple(blob):
  text = str(blob) # blob may be utf8
  termux.Clipboard.setclipboard(blob)

def empty_clipboard(ui):
  termux.Clipboard.setclipboard('')
  ui.status('Clipboard Cleared', append=True)

def sendViaClipboardSimple(blobs, record = None, ui=ui_null()):
  def tty_ui_loop(ui):
    ui_fds = ui.mainloop.screen.get_input_descriptors()
    if ui_fds is None: ui_fds = []
    select_fds = set(ui_fds)

    old = ui_tty.set_cbreak() # Set unbuffered IO (if not already)
    try:
      while 1:
        ui.mainloop.draw_screen()
        while True:
          try:
            timeout = None
            (readable, ign, ign) = select.select(select_fds, [], [], timeout)
          except select.error as e:
            if e.args[0] == 4: continue # Interrupted system call
            raise
          break

        if not readable:
          break

        for fd in readable:
          if fd == sys.stdin.fileno():
            char = sys.stdin.read(1)
            if char == '\n':
              return True
            elif char == '\x1b':
              return False
          elif fd in ui_fds:
            # This is a hack to redraw the screen - we really should
            # restructure all this so as not to block instead:
            ui.mainloop.event_loop._loop()
    finally:
      ui_tty.restore_cbreak(old)
  ui.status('')
  for (field, blob) in blobs:
    copy_text_simple(blob)
    ui.status("Copied %s for '%s' to clipboard, press enter to continue..."%(field.upper(),record), append=True)
    if not tty_ui_loop(ui):
      break
  empty_clipboard(ui)

# TODO: Implement advanced clipboard
sendViaClipboard = sendViaClipboardSimple

if __name__ == '__main__':
  args = sys.argv[1:] if sys.argv[1:] else ['usage: ' , sys.argv[0], ' { strings }']
  blobs = list(zip([ "Item %i"%x for x in range(len(args)) ], args))
  sendViaClipboardSimple(blobs, ui=ui_tty())
