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
import time

# If winclipboard.py takes longer than this to respond, warn that Windows
# Defender might be slowing things down. Typical times are about 0.15 seconds:
excessive_time = 0.8

class WSLClipboardProxy(object):
  def __init__(self, ui):
    start_time = time.time()
    self.winpython = subprocess.Popen("python.exe winclipboard.py -".split(),
        cwd=os.path.dirname(os.path.realpath(sys.argv[0])),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE)#, stderr=subprocess.PIPE)
    #os.set_blocking(self.winpython.stdout.fileno(), False)
    self.winpython.stdout.read(1)
    delta_time = time.time() - start_time
    if delta_time > excessive_time:
      wsl_distro = os.environ.get('WSL_DISTRO_NAME', 'Ubuntu')
      ui.status('WSL clipboard proxy took %.2f seconds to start\n' \
      'Please ensure WSL paths are added to Windows Defender exclusions\n' \
      'e.g. for WSL2 add \\\\wsl.localhost\\%s\\' % (delta_time, wsl_distro), append=True)

  def __del__(self):
    if self.winpython:
      #self.winpython.stdin.close()
      self.winpython.terminate()
      self.winpython.wait()

  def queue(self, blob, field=None, record=None):
    # TODO: Maybe restart proxy if has been killed externally?
    buf = blob.encode('utf8')
    if field is not None:
      buf += b'\x1f' + field.encode('utf8')
    if record is not None:
      buf += b'\x1e' + record.encode('utf8')
    self.winpython.stdin.write(buf + b'\n')
    self.winpython.stdin.flush()

  def queue_eot(self):
    self.queue('\x18') # Clear clipboard
    self.queue('\x04') # EOT

  def skip(self):
    self.winpython.stdin.write(b'\x0f\n') # Skip
    self.winpython.stdin.flush()

  def cancel(self):
    self.winpython.stdin.write(b'\x1b\n') # Cancel
    self.winpython.stdin.flush()

def init(ui):
  global proxy
  proxy = WSLClipboardProxy(ui)

def copy_text_simple(blob):
  text = str(blob).encode('utf8') # blob may be utf8
  subprocess.run("clip.exe", input=text)

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
        if fd == sys.stdin.fileno() \
            or (hasattr(fd, 'name') and fd.name == '<stdin>'): # Pre-emptive fix
          char = sys.stdin.read(1)
          if char == '\n':
            if proxy_io:
              proxy.skip()
            else:
              return True
          elif char == '\x1b':
            if proxy_io:
              proxy.cancel()
            else:
              return False
        elif fd in proxy_io:
          # fd.readline() is problematic, since it is an io.BufferedReader that
          # might drain extra data from the pipe and hold it in its internal
          # buffer, but doesn't appear to offer us a way to determine if this
          # has happened. Since that may mean there is no data in the pipe,
          # select won't report the fd as readable and we can end up getting
          # stuck because we don't know we need to call readline again to drain
          # the BufferedReader. Use low level IO to drain the pipe ourselves
          # and process until we are done.
          #status = fd.readline()
          buf = os.read(fd.fileno(), 4096)
          for status in buf.splitlines():
            #if status == b'': # Don't use this - fooled by proxy sending empty line
            if status in (b'\x04\r\n', b'\x04\n', b'\x04'): # FIXME: Should only need one
              return True
            ui.status(status.decode('utf8').strip(), append=True)
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
    proxy.queue(blob, field, record)
  proxy.queue_eot()
  tty_ui_loop(ui, [proxy.winpython.stdout])
  #empty_clipboard(ui) # Slow and can throw error when using proxy

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
  init()
  sendViaClipboard(blobs, ui=ui_tty())
