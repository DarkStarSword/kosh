#!/usr/bin/env python3
# vi:sw=2:ts=2:sts=2:expandtab

# In thoery WSL 2 on Windows 11 can use Xlib (provided necessary drivers, etc
# are installed and WSL is updated) and clipboard is supposed to work through
# that... but it doesn't seem to work for me... For now, call out to clip.exe
# to handle clipboard, though this unfortunately means we can only use the
# basic clipboard implementation.

from ui import ui_tty, ui_null
import sys
import os
import select
import subprocess

def copy_text_simple(blob):
  text = str(blob).encode('utf8') # blob may be utf8
  subprocess.run("clip.exe", input=text)

def copy_text_wsl_proxy(blob):
  #native_python = subprocess.run("python.exe winclipboard.py -".split(), input=blob)
  winpython = subprocess.Popen("python.exe winclipboard.py -".split(),
      cwd=os.path.dirname(os.path.realpath(sys.argv[0])),
      stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  winpython.stdin.write(blob.encode('utf8'))
  winpython.stdin.close()
  return winpython

def empty_clipboard(ui):
  copy_text_simple("")
  ui.status('Clipboard Cleared', append=True)

def tty_ui_loop(ui, proxy_io=[]):
  ui_fds = ui.mainloop.screen.get_input_descriptors()
  if ui_fds is None: ui_fds = []
  select_fds = set(ui_fds + proxy_io)

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
        elif fd in proxy_io:
          status = fd.readline()
          if status == b'':
            return True
          # TODO: Show status messages (e.g. for clipboard copy ignored within ..ms),
          # but only once the 'Ready to send' message is coming through at right time:
          #ui.status(status.decode('utf8').strip(), append=True)
        elif fd in ui_fds:
          # This is a hack to redraw the screen - we really should
          # restructure all this so as not to block instead:
          ui.mainloop.event_loop._loop()
  finally:
    ui_tty.restore_cbreak(old)

def sendViaClipboardSimple(blobs, record = None, ui=ui_null()):
  ui.status('')
  for (field, blob) in blobs:
    copy_text_simple(blob)
    ui.status("Copied %s for '%s' to clipboard, press enter to continue..."%(field.upper(),record), append=True)
    if not tty_ui_loop(ui):
      break
  empty_clipboard(ui)

def sendViaClipboard(blobs, record = None, ui=ui_null()):
  ui.status('')
  for (field, blob) in blobs:
    child = copy_text_wsl_proxy(blob)
    try:
      ui.status("Ready to send %s for '%s'... (enter skips, escape cancels)"%(field.upper(),record), append=True)
      if not tty_ui_loop(ui, [child.stdout]):
        break
    finally:
      if child:
        child.terminate()
        child.wait()
  empty_clipboard(ui)

def native_python_is_stub():
  # .exe extension will run native Windows Python if found in path. Pass
  # an argument so it doesn't try to open Windows Store to install it.
  try:
    native_python = subprocess.run("python.exe --version".split(), capture_output=True)
  except FileNotFoundError:
    # winstore Stub not enabled, nor native Python found in PATH
    return None
  # Seen both return codes 49 and 4 from stub, so not sure if it's actually
  # defined... Assume any non-zero return code means it was (probably) the stub
  return native_python.returncode != 0

def attempt_install_winstore_python():
  # Running python.exe without arguments will open winstore to install it if
  # the alias is enabled in settings -> Manage App Execution Aliases
  subprocess.run("python.exe")

if __name__ == '__main__':
  args = sys.argv[1:] if sys.argv[1:] else ['usage: ' , sys.argv[0], ' { strings }']
  blobs = list(zip([ "Item %i"%x for x in range(len(args)) ], args))
  #sendViaClipboardSimple(blobs, ui=ui_tty())
  sendViaClipboard(blobs, ui=ui_tty())
