#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab

try:
  from Xlib import X, Xatom, error as Xerror
  import Xlib.display
  defSelections = [Xatom.PRIMARY, Xatom.SECONDARY, 'CLIPBOARD']
except ImportError:
  print 'Error importing python-Xlib, X clipboard integration will be unavailable'
  defSelections = None

from select import select

class XlibNotFound(Exception): pass
class XFailConnection(Exception): pass

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

def _sendSelection(blob, type, size, event):
  """
  Positively respond to a selection request (event) by passing the blob of type
  type (with appropriate format size for the type - refer to the ICCCM) to the
  requester specified in the event.
  """
  print 'Sending', blob, 'to', event
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

def sendViaClipboard(blobs, selections = defSelections):
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

  def handleSelectionRequest(e):
    if ((e.time != X.CurrentTime and e.time < timestamp) or # Timestamp out of bounds
        (e.selection not in selections) or # Requesting a different selection
        (e.owner != win)): # We aren't the owner
      _refuseSelectionRequest(e)
      return False
    if (e.target in (Xatom.STRING, XA_TEXT)):
      # TODO: Get window title and/or command line and host to report
      oldmask = e.requestor.get_attributes().your_event_mask
      e.requestor.change_attributes(event_mask = oldmask | X.PropertyChangeMask)
      _sendSelection(blob, Xatom.STRING, 8, e)
      return True
    elif (e.target == XA_TIMESTAMP): #untested
      print 'Untested XA_TIMESTAMP'
      _sendSelection(timestamp, XA_TIMESTAMP, 32, e)
    elif (e.target == XA_TARGETS): #untested
      print 'Untested XA_TARGETS'
      _sendSelection([Xatom.STRING, XA_TEXT, XA_TIMESTAMP, XA_TARGETS], XA_TARGETS, 32, e)
    else:
      _refuseSelectionRequest(e)
    return False

  if type(blobs) == type(''): blobs = [blobs]
  try:
    display = Xlib.display.Display()
  except Xerror.DisplayError:
    raise XFailConnection()
  screen = display.screen()
  win = screen.root.create_window(0,0,1,1,0,0)

  XA_TEXT = display.intern_atom('TEXT', True)
  XA_TARGETS = display.intern_atom('TARGETS', True)
  XA_TIMESTAMP = display.intern_atom('TIMESTAMP', True)

  try:
    for blob in blobs:
      awaitingCompletion = []
      timestamp = _ownSelections(display, win, selections)

      timeout = None
      while 1:
        (readable, ign, ign) = select([display], [], [], timeout)
        
        if not readable and awaitingCompletion == []:
          break

        if display in readable:
          while display.pending_events():
            e = display.next_event()
            if e.type == X.SelectionRequest:
              if handleSelectionRequest(e):
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
        # TODO: Keyboard input...
  finally:
    win.destroy()

if __name__ == '__main__':
  sendViaClipboard(['testuser','secret'])
