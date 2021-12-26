#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab

# Copyright (C) 2009-2021 Ian Munsie
#
# Kosh is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Kosh is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Kosh.  If not, see <http://www.gnu.org/licenses/>.

Xlib = None
import select
import re
from ui import ui_tty, ui_null

defSelections = ['PRIMARY', 'SECONDARY', 'CLIPBOARD']
blacklist = ['klipper', 'xclipboard', 'wmcliphist', '<unknown>', 'qtcreator', 'diodon']
blacklist_re = list(map(re.compile, [
  'TightVNC: .*', # Still works (F8->local->remote requests as "popup@None") until it steals the PRIMARY selection
]))
# TODO: Option to re-grab if PRIMARY selection is stolen. Maybe blacklist certain apps like TightVNC?

class XFailConnection(Exception): pass

_prev_requestor = None

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
  return False

def _sendSelection(blob, type, size, event, ui):
  """
  Positively respond to a selection request (event) by passing the blob of type
  type (with appropriate format size for the type - refer to the ICCCM) to the
  requester specified in the event.
  """
  err = Xerror.CatchError()
  prop = event.property if event.property else event.target
  if type in (Xatom.STRING, Xatom.TEXT):
    blob = str(blob) # blob may be utf8
  event.requestor.change_property(prop, type, size, blob, onerror=err)
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
    owner = display.get_selection_owner(selection)
    if owner.id != win.id:
      raise Exception('Failed to make %s own selection %i, owned by %s' % (win, selection, owner))
  return timestamp

def sendViaClipboard(blobs, record = None, txtselections = defSelections, ui=ui_null(), auto_advance=True):
  """
  Send a list of blobs via the clipboard (using X selections, cut buffers are
  not yet supported) in sequence. Typically the PRIMARY and/or SECONDARY
  selections are used for middle click and shift+insert pasting, while the
  CLIPBOARD selection is often used by Ctrl+V pasting.

  Raises an XFailConnection exception if connecting to the X DISPLAY failed.
  """
  global Xlib, X, Xatom, Xerror
  if Xlib is None:
    ui.status('Initialising python-Xlib, stand by...')
    ui.mainloop.draw_screen()
    try:
      from Xlib import X, Xatom, error as Xerror
      import Xlib.display
    except ImportError:
      ui.status('Error importing python-Xlib, X clipboard integration unavailable')
      return

  # Can't do this in the function definition - it seems that a .remove()
  # affects the default. That would be expected if it were assigned as a
  # reference to the default list, but even happens when the [:] syntax is
  # used to copy the list. I guess that must be an unexpected side effect of
  # the function definition only excuting once when the file is loaded?
  txtselections = txtselections[:]
  selections = txtselections[:]

  def findClientWindow(window, ui):
    """ walk up the tree looking for a client window """

    def get_wm_client_leader(window):
        d = window.get_full_property(Xatom.WM_CLIENT_LEADER, Xatom.WINDOW)
        if d is None or d.format != 32 or len(d.value) < 1:
          return None
        else:
          cls = window.display.get_resource_class('window', type(window))
          return cls(window.display, d.value[0])

    host = window.get_wm_client_machine()
    while True:
      comm = window.get_full_property(Xatom.WM_COMMAND, Xatom.STRING)
      name = window.get_wm_name()
      # Nokia N900 uses _NET_WM_NAME instead of WM_NAME:
      netname = window.get_full_property(Xatom._NET_WM_NAME, Xatom.UTF8_STRING)
      leadercomm = None

      # Only one top-level window for a given client has WM_COMMAND. Find the
      # leader top-level window (if we are looking at a top-level window) and
      # check it's WM_COMMAND property.
      #
      # I don't see a requirement in the ICCCM that the client leader
      # necessarily be the window with the WM_COMMAND property, it may end up
      # being necessary to iterate all the windows with the same
      # WM_CLIENT_LEADER to find the one window that has the WM_COMMAND.
      leader = get_wm_client_leader(window)
      if leader is not None and leader != window:
        leadercomm = leader.get_full_property(Xatom.WM_COMMAND, Xatom.STRING)

      requestor = name or netname or comm or leadercomm
      if hasattr(requestor, 'value'):
        requestor = requestor.value
      if requestor:
        break
      resp = window.query_tree()
      root = resp.root; parent = resp.parent
      if parent == root:
        return ('<unknown>', host)
      window = parent
    return (requestor, host)

  def handleSelectionRequest(e, field, record, ui):
    global _prev_requestor
    if ((e.time != X.CurrentTime and e.time < timestamp) or # Timestamp out of bounds
        (e.selection not in selections) or # Requesting a different selection
        (e.owner.id != win.id)): # We aren't the owner
      return _refuseSelectionRequest(e)
    if (e.target in (Xatom.STRING, Xatom.TEXT)):
      (requestor, host) = findClientWindow(e.requestor, ui)
      if requestor.lower() in blacklist or any([ pattern.match(requestor) for pattern in blacklist_re ]):
        if requestor != _prev_requestor:
          ui.status("Ignoring request from %s@%s"%(requestor, host), append=True)
          _prev_requestor = requestor
        return _refuseSelectionRequest(e)
      ui.status("Sent %s for '%s' via %s to %s@%s"%(field.upper(), record, display.get_atom_name(e.selection), requestor, host), append=True)
      oldmask = e.requestor.get_attributes().your_event_mask
      e.requestor.change_attributes(event_mask = oldmask | X.PropertyChangeMask)
      _sendSelection(blob, Xatom.STRING, 8, e, ui)
      return True
    elif (e.target == Xatom.TIMESTAMP):
      _sendSelection([timestamp], Xatom.TIMESTAMP, 32, e, ui)
    elif (e.target == Xatom.TARGETS):
      _sendSelection([Xatom.TARGETS, Xatom.TIMESTAMP, Xatom.TEXT, Xatom.STRING], Xatom.ATOM, 32, e, ui)
    else:
      return _refuseSelectionRequest(e)
    return False

  # Opening the display prints 'Xlib.protocol.request.QueryExtension' to
  # stdout, so temporarily redirect it:
  ui.status('Connecting to display, stand by...')
  ui.mainloop.draw_screen()
  import sys, io
  saved_stdout = sys.stdout
  sys.stdout = io.StringIO()
  try:
    display = Xlib.display.Display()
  except Xerror.DisplayError:
    raise XFailConnection()
  finally:
    sys.stdout = saved_stdout
  screen = display.screen()
  win = screen.root.create_window(0,0,1,1,0,0)

  Xatom.TEXT = display.intern_atom('TEXT', True)
  Xatom.TARGETS = display.intern_atom('TARGETS', True)
  Xatom.TIMESTAMP = display.intern_atom('TIMESTAMP', True)
  Xatom.WM_CLIENT_LEADER = display.intern_atom('WM_CLIENT_LEADER', True)
  Xatom._NET_WM_NAME = display.intern_atom('_NET_WM_NAME', True)
  Xatom.UTF8_STRING = display.intern_atom('UTF8_STRING', True)

  ui_fds = ui.mainloop.screen.get_input_descriptors()
  if ui_fds is None: ui_fds = []
  select_fds = set([display] + ui_fds)
  try:
    old = ui_tty.set_cbreak() # Set unbuffered IO (if not already)
    ui.status('')
    for (field, blob) in blobs:
      ui.status("Ready to send %s for '%s' via %s... (enter skips, escape cancels)"%(field.upper(),record,str(txtselections)), append=True)
      ui.mainloop.draw_screen()
      awaitingCompletion = []
      timestamp = _ownSelections(display, win, selections)

      timeout = None
      skip = False
      while 1:
        if skip and awaitingCompletion == []: break
        while True:
          try:
            (readable, ign, ign) = select.select(select_fds, [], [], timeout)
          except select.error as e:
            if e.args[0] == 4: continue # Interrupted system call
            raise
          break

        if not readable and awaitingCompletion == []:
          break

        for fd in readable:
          if fd == sys.stdin.fileno():
            char = sys.stdin.read(1)
            if char == '\n':
              skip = True
            elif char == '\x1b':
              return
          elif fd in ui_fds:
            # This is a hack to redraw the screen - we really should
            # restructure all this so as not to block instead:
            ui.mainloop.event_loop._loop()

          if fd == display:
            while display.pending_events():
              e = display.next_event()
              if e.type == X.SelectionRequest:
                if handleSelectionRequest(e, field, record, ui) and auto_advance:
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
                  # If we lost CLIPBOARD (explicit copy) or no longer control any selection, abort:
                  name = display.get_atom_name(e.atom)
                  selections.remove(e.atom)
                  txtselections.remove(name)
                  if name == 'CLIPBOARD' or not selections:
                    # If transfer is in progress it should be allowed to complete:
                    if awaitingCompletion == []: return
                    timeout = 0.01
                  else:
                    ui.status("Lost control of %s, still ready to send %s via %s..."%(name, field.upper() ,str(txtselections)), append=True)
                    ui.mainloop.draw_screen()
            ui.mainloop.draw_screen()
  finally:
    ui_tty.restore_cbreak(old)
    win.destroy()
    display.close() # I may have introduced a bug while adding the urwid loop
                    # stuff here - the clipboard selection remained grabbed
                    # after destroying the window. This worked around it since
                    # I can't see what is wrong.
    ui.status('Clipboard Cleared', append=True)

if __name__ == '__main__':
  import sys
  args = sys.argv[1:] if sys.argv[1:] else ['usage: ' , sys.argv[0], ' { strings }']
  sendViaClipboard(list(zip([ "Item %i"%x for x in range(len(args)) ], args)), ui=ui_tty())
