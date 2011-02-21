#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab

try:
  from Xlib import X, Xatom, error as Xerror
  import Xlib.display
  defSelections = [Xatom.PRIMARY, Xatom.SECONDARY, 'CLIPBOARD']
except ImportError:
  print 'Error importing python-Xlib, X clipboard integration will be unavailable'
  defSelections = None

import select

class XlibNotFound(Exception): pass
class XFailConnection(Exception): pass

class ui_null(object):
  """
  Dummy class that will do nothing when called, and return itself as any of
  it's attributes.  Intended to be used in place of a ui class where no
  interaction is to take place. Calls such as ui_null().mainloop.foo.bar.baz()
  will not raise any exceptions.
  """
  def __call__(self, *args): pass
  def __getattribute__(self,name):
    return self

# FIXME: This shouldn't be here, and needs to be expanded
class ui_tty(object):
  def status(self, msg):
    print msg


def newTimestamp(display, window):
  """
  Appends a property with zero length data and obtains a timestamp from the
  corresponding PropertyNotify event.

  WARNING: Other events will be discarded by this method
  """
  oldmask = window.get_attributes().your_event_mask
  window.change_attributes(event_mask = X.PropertyChangeMask)
  atom = Xatom.FULL_NAME # Arbitrary. Bad example? Blatantly incorrect? Probably - I'm an X n00b
  window.change_property(atom, Xatom.STRING, 8, '', X.PropModeAppend)
  while 1:
    e = display.next_event()
    if e.type == X.PropertyNotify and e.window == window and e.atom == Xatom.FULL_NAME:
      window.change_attributes(event_mask = oldmask)
      return e.time

def _refuseSelectionRequest(event):
  """
  Respond to a selection request with an empty property to reject the
  selection request.
  """
  resp = Xlib.protocol.event.SelectionNotify(
      requestor = event.requestor,
      selection = event.selection,
      target = event.target,
      property = 0,
      time = event.time)
  event.requestor.send_event(resp, 0, 0)

def _sendSelection(blob, type, size, event, ui):
  """
  Positively respond to a selection request (event) by passing the blob of type
  type (with appropriate format size for the type - refer to the ICCCM) to the
  requester specified in the event.
  """
  #ui.status('DEBUG: Sending %s to %s'%(repr(blob),event))
  err = Xerror.CatchError()
  prop = event.property if event.property else event.target
  event.requestor.change_property(prop, type, size, str(blob), onerror=err)
  if err.get_error():
    _refuseSelectionRequest(event)
    raise Exception(str(err.get_error()))
  resp = Xlib.protocol.event.SelectionNotify(
      requestor = event.requestor,
      selection = event.selection,
      target = event.target,
      property = prop,
      time = event.time)
  event.requestor.send_event(resp, 0, 0)

def _ownSelections(display, win, selections):
  """
  Have the window take ownership of a list of selections on the given display.

  Selections can be an atom or the name of an atom. If the name of an atom is
  provided, it's entry in the selections list will be replaced by the atom it
  resolves to.
  """
  timestamp = newTimestamp(display, win)
  for (i,selection) in enumerate(selections):
    if type(selection) == type(''):
      selection = selections[i] = display.intern_atom(selection, False)
    win.set_selection_owner(selection, timestamp)
    if display.get_selection_owner(selection) != win:
      raise Exception('Failed to own selection %i' % selection)
  return timestamp

def sendViaClipboard(blobs, selections = defSelections, ui=ui_null()):
  """
  Send a list of blobs via the clipboard (using X selections, cut buffers are
  not yet supported) in sequence. Typically the PRIMARY and/or SECONDARY
  selections are used for middle click and shift+insert pasting, while the
  CLIPBOARD selection is often used by Ctrl+V pasting.

  Raises an XlibNotFound exception if python-xlib failed to import.
  Raises an XFailConnection exception if connecting to the X DISPLAY failed.
  """

  try: Xlib
  except NameError: raise XlibNotFound()

  def handleSelectionRequest(e, ui):
    if ((e.time != X.CurrentTime and e.time < timestamp) or # Timestamp out of bounds
        (e.selection not in selections) or # Requesting a different selection
        (e.owner != win)): # We aren't the owner
      _refuseSelectionRequest(e)
      return False
    if (e.target in (Xatom.STRING, XA_TEXT)):
      # TODO: Get window title and/or command line and host to report
      oldmask = e.requestor.get_attributes().your_event_mask
      e.requestor.change_attributes(event_mask = oldmask | X.PropertyChangeMask)
      _sendSelection(blob, Xatom.STRING, 8, e, ui)
      return True
    elif (e.target == XA_TIMESTAMP): #untested
      ui.status('INFO: Untested XA_TIMESTAMP')
      _sendSelection(timestamp, XA_TIMESTAMP, 32, e, ui)
    elif (e.target == XA_TARGETS): # This *seems* to work... though I am unconfident that the length is sent correctly. There may be a better way to do this.
      import struct
      _sendSelection(struct.pack('IIII', *map(lambda x: int(x), [XA_TARGETS, XA_TIMESTAMP, XA_TEXT, Xatom.STRING])), XA_TARGETS, 32, e, ui)
    else:
      _refuseSelectionRequest(e)
    return False

  if type(blobs) == type(''): blobs = [blobs]

  # Opening the display prints 'Xlib.protocol.request.QueryExtension' to
  # stdout, so temporarily redirect it:
  import sys, StringIO
  saved_stdout = sys.stdout
  sys.stdout = StringIO.StringIO()
  try:
    display = Xlib.display.Display()
  except Xerror.DisplayError:
    raise XFailConnection()
  finally:
    sys.stdout = saved_stdout
  screen = display.screen()
  win = screen.root.create_window(0,0,1,1,0,0)

  XA_TEXT = display.intern_atom('TEXT', True)
  XA_TARGETS = display.intern_atom('TARGETS', True)
  XA_TIMESTAMP = display.intern_atom('TIMESTAMP', True)

  ui_fds = ui.mainloop.screen.get_input_descriptors()
  if ui_fds is None: ui_fds = []
  select_fds = set([display] + [sys.stdin] + ui_fds)
  ui.status('Ready to send credentials via %s... (enter skips, escape cancels)'%str(selections))
  ui.mainloop.draw_screen()
  try:
    for blob in blobs:
      awaitingCompletion = []
      timestamp = _ownSelections(display, win, selections)

      timeout = None
      skip = False
      while 1:
        if skip and awaitingCompletion == []: break
        while True:
          try:
            (readable, ign, ign) = select.select(select_fds, [], [], timeout)
          except select.error,e:
            if e.args[0] == 4: continue # Interrupted system call
            raise
          break

        if not readable and awaitingCompletion == []:
          break

        for fd in readable:
          if fd == sys.stdin:
            char = sys.stdin.read(1)
            if char == '\n':
              ui.status('Skipping...')
              skip = True
            elif char == '\x1b':
              ui.status('Cancelled')
              return
          elif fd in ui_fds:
            ui.mainloop._update()

          if fd == display:
            while display.pending_events():
              e = display.next_event()
              if e.type == X.SelectionRequest:
                if handleSelectionRequest(e, ui):
                  # Don't break immediately, transfer will not have finished.
                  # Wait until the property has been deleted by the requestor
                  awaitingCompletion.append((e.requestor, e.property))
              elif e.type == X.PropertyNotify:
                if (e.window, e.atom) in awaitingCompletion \
                    and e.state == 1: # Deleted
                  awaitingCompletion.remove((e.window, e.atom))
                  # Some programs, such as firefox (when pasting with
                  # shift+insert), don't expect the selection to change suddenly
                  # and behave badly if it does, so wait a moment before ending:
                  timeout = 0.01
              elif e.type == X.SelectionClear:
                if e.time == X.CurrentTime or e.time >= timestamp:
                  # If transfer is in progress it should be allowed to complete:
                  if awaitingCompletion == []: return
                  timeout = 0.01
            ui.mainloop.draw_screen()
  finally:
    win.destroy()
    display.close() # I may have introduced a bug while adding the urwid loop
                    # stuff here - the clipboard selection remained grabbed
                    # after destroying the window. This worked around it since
                    # I can't see what is wrong.
    ui.status('Clipboard Cleared')

if __name__ == '__main__':
  import sys
  args = sys.argv[1:] if sys.argv[1:] else ['usage:' , sys.argv[0], ' { strings }']
  sendViaClipboard(args, ui=ui_tty())
