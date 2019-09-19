#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab

from __future__ import print_function
from ui import ui_tty, ui_null
import sys
import select

def sendViaClipboard(blobs, record = None, ui=ui_null()):
  try:
    import ctypes
    user32 = ctypes.CDLL("user32.dll")
    kernel32 = ctypes.CDLL("kernel32.dll")
  except:
    return

  # TODO: Setting handle to NULL and respond to WM_RENDERFORMAT on a hidden
  # window might give us a way to know when the clipboard is about to be
  # pasted. A small delay after that might be enough to give equivelent
  # functionality to Linux

  def copy_text(blob):
    text = str(blob) + '\0' # blob may be utf8

    hwnd = None
    rc = user32.OpenClipboard(hwnd)
    if not rc:
      return

    user32.EmptyClipboard()

    GMEM_MOVEABLE = 2
    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(text))
    buf = kernel32.GlobalLock(handle)
    ctypes.memmove(buf, text, len(text))
    kernel32.GlobalUnlock(handle)

    CF_TEXT = 1
    user32.SetClipboardData(CF_TEXT, handle)
    user32.CloseClipboard()

  def empty_clipboard(ui):
    user32.OpenClipboard(None)
    user32.EmptyClipboard()
    user32.CloseClipboard()
    ui.status('Clipboard Cleared', append=True)

  def ui_loop(ui):
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
    copy_text(blob)
    ui.status("Copied %s for '%s' to clipboard, press enter to continue..."%(field.upper(),record), append=True)
    if not ui_loop(ui):
      break

  empty_clipboard(ui)
