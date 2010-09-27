#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab

try:
  from Xlib import X, Xatom, error as Xerror
  import Xlib.display
except ImportError:
  raise

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

def refuseSelectionRequest(event):
  #print 'Refusing', event
  resp = Xlib.protocol.event.SelectionNotify(
      requestor = event.requestor,
      selection = event.selection,
      target = event.target,
      property = 0,
      time = event.time)
  event.requestor.send_event(resp, 0, 0)

def sendSelection(blob, event):
  print 'Sending', blob, 'to', event
  prop = event.property if event.property else event.target
  event.requestor.change_property(prop, Xatom.STRING, 8, blob)
  resp = Xlib.protocol.event.SelectionNotify(
      requestor = event.requestor,
      selection = event.selection,
      target = event.target,
      property = prop,
      time = event.time)
  event.requestor.send_event(resp, 0, 0)

def main(blobs, selections = [Xatom.PRIMARY, Xatom.SECONDARY]):
  if type(blobs) == type(''): blobs = [blobs]
  try:
    display = Xlib.display.Display()
  except Xerror.DisplayError:
    raise
  screen = display.screen()
  win = screen.root.create_window(0,0,1,1,0,0)

  try:
    for blob in blobs:
      timestamp = newTimestamp(display, win)

      for selection in selections: # FIXME: CLIPBOARD selection
        win.set_selection_owner(selection, timestamp)
        if display.get_selection_owner(selection) != win:
          raise Exception('Failed to own selection %i' % selection)

      while 1:
        e = display.next_event()

        if e.type == X.SelectionRequest:
          if ((e.time != X.CurrentTime and e.time < timestamp) or # Timestamp out of bounds
              (e.selection not in selections) or # Requesting a different selection
              (e.owner != win) or # We aren't the owner
              (e.target != Xatom.STRING)): # Unsupported target
            # FIXME: Maybe support TARGETS, TIMESTAMP, TEXT like pwsafe
            # FIXME: Required to support TARGETS by ICCCM
            refuseSelectionRequest(e)
            continue 

          sendSelection(blob, e)
          #break # FIXME: Must await confirmation that data has been received

        if e.type == X.SelectionClear:
          if e.time == X.CurrentTime or e.time >= timestamp:
            # XXX If transfer is in progress it should be allowed to complete
            return # All selection ownerships will be released when window is destroyed
  finally:
    win.destroy()

if __name__ == '__main__':
  #main(['goobar','secret'])
  main('foo')
  main('bar')

    #win.list_properties()


    # Get timestamp to use with SetS

    #SetSelectionOwner(Xatom.PRIMARY, win, timestamp)
    #owner = GetSelectionOwner(Xatom.PRIMARY)
    #if (owner != Window):
    #  Failure

    #receive SelectionRequest event
    #  If timestamp invalid refuse by sending requestor a SelectionNotify with property set to None (SendEvent request with empty event mask)
    #  If property is None requestor is an obsolete client - use target atom as property name for the reply
    #  Otherwise use target to decide on form into which selection is to be converted (parameters in property depending on definition of target)
    #  If selection cannot be converted to target form, refuse as above

    #  If property is not none, place the result of conversion into specified property on requestor window and set property type to appropriate value (need not be the same as specified target)
    #  If failure, must refuse as above

    #  If property successfully stored, acknowledge by sending SelectionNotify event (SendEvent with empty mask) - selection,target,time,property should be set to values from SelectionRequest (Note: property set to None indicates conversion fail)

    #  No need to worry about deleting resource - requestor is responsible for that by convention
    #  Can express interest in PropertyNotify event for requestor window and wait until property has been deleted before assuming selection data transferred.


    #  When another client gains ownership of selection, receive SelectionClear event

    #  Give up ownership with SetSelectionOwner, owner specified as None and timestamp as original

