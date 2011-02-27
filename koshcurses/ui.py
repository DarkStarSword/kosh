#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab

import urwid
import weakref
import widgets
import time

class passwordList(widgets.keymapwid, urwid.WidgetWrap):
  keymap = {
      'f5': 'showOlder',
      'f6': 'showNewer',
      'y': 'yank',
      'e': 'edit',
      }

  def __init__(self, db, pwForm, ui):
    self.db = db
    self.pwForm = pwForm
    self.ui = ui
    self.visibleEntries = self.db
    self.refresh()
    urwid.WidgetWrap.__init__(self, self.lb)

  def refresh(self):
    def cicmp(x, y):
      return cmp(x.lower(), y.lower())
    self.content = [ urwid.Button(x, self.select) for x in sorted(self.visibleEntries, cicmp) ]
    self.lb = urwid.ListBox(self.content)
    self.selection = 0
    self._set_w(self.lb)
    if len(self.visibleEntries):
      self.showing = self.visibleEntries[self.lb.get_focus()[0].get_label()]
      self.pwForm.show(self.showing)

  def keypress(self, size, key):
    ret = super(passwordList, self).keypress(size, key)
    if ret is not None:
      # FIXME: generalise these, handle tab better:
      if key in ['j']: return self.keypress(size, 'down')
      if key in ['k']: return self.keypress(size, 'up')
      if key in ['h']: return self.keypress(size, 'left')
      if key in ['l', 'tab']: return self.keypress(size, 'right')
      # FIXME: edit, delete, yank
    selection = self.lb.get_focus()
    if selection[0] and selection[1] != self.selection:
      self.showing = self.db[selection[0].get_label()]
      self.pwForm.show(self.showing)
      self.selection = selection[1]
    return ret

  def select(self, button):
    self.pwForm.reveal(self.showing)
    # FIXME: focus

  def showOlder(self, size, key):
    if self.showing.older is not None:
      self.showing = self.showing.older
      self.pwForm.show(self.showing)

  def showNewer(self, size, key):
    if self.showing.newer is not None:
      self.showing = self.showing.newer
      self.pwForm.show(self.showing)

  def yank(self, size, key):
    import xclipboard
    xclipboard.sendViaClipboard(self.showing.clipIter(), ui=self.ui)

  def edit(self, size, key):
    self.pwForm.edit(self.showing.clone(), self.ui.commitNew, self.ui.cancel)

  def search(self, search):
    import string
    if not search:
      self.visibleEntries = self.db
      ret = None
    else:
      self.visibleEntries = {}
      for entry in self.db:
        # FIXME: Don't (optionally?) search on other protected fields
        if reduce(lambda x,y: x or search.lower() in y, map(string.lower,
          [entry]+[v for (k,v) in self.db[entry].items()
            if k.lower() not in ['password']]), False):
            self.visibleEntries[entry] = self.db[entry]
      ret = len(self.visibleEntries)
    self.refresh()
    return ret

class passwordForm(urwid.WidgetWrap):
  def __init__(self):
    urwid.WidgetWrap.__init__(self, urwid.SolidFill())
    self.lb = None

  def show(self, entry):
    self.entry = entry
    self.content = [urwid.Text('Name: ' + self.entry.name)] + \
      [ urwid.Button(x) for x in entry ] + \
      [ urwid.Divider(), urwid.Text('Timestamp: ' + time.asctime(time.localtime(entry.timestamp()))) ]
    self._update()

  def reveal(self, entry):
    self.entry = entry
    self.content = [urwid.Text('Name: ' + self.entry.name)] + \
      [ urwid.Text(x+": " + entry[x]) for x in entry ] + \
      [ urwid.Divider(), urwid.Text('Timestamp: ' + time.asctime(time.localtime(entry.timestamp()))) ]
    self._update()

  def edit(self, entry, ok, cancel):
    self.entry = entry
    self.cancel = cancel
    self.okCallback=ok
    self.fname = widgets.koshEdit('Name: ', self.entry.name)
    self.fields = [ widgets.passwordEdit(x+": ", entry[x], revealable=True) for x in entry ]
    self.newfield = widgets.koshEdit('Add new field: ')
    self.content = [self.fname] + self.fields + [urwid.Divider(), self.newfield] + [ urwid.GridFlow(
          [urwid.Button('Save', self.commit),
            urwid.Button('Cancel', self.discard) ],
          10, 3, 1, 'center')
      ]
    self._update()

  def add_new_field(self):
    field = self.newfield.get_edit_text().strip()
    if not field: return
    if field in self.entry: return
    self.entry[field] = ''
    self.fields += [ widgets.passwordEdit(field+': ', '', revealable=True) ]
    self.content = [self.fname] + self.fields + [urwid.Divider(), self.newfield] + [ urwid.GridFlow(
          [urwid.Button('Save', self.commit),
            urwid.Button('Cancel', self.discard) ],
          10, 3, 1, 'center')
      ]
    self._update()
    #self._w.set_focus(self.newfield)

  def validate(self):
    return self.fname.get_edit_text() != ''

  def commit(self, *args):
    if not self.validate():
      # FIXME: Notify
      return
    self.entry.name = self.fname.get_edit_text()
    for field in self.fields:
      name = field.caption[:-2]
      txt = field.get_edit_text()
      if txt == '':
        del self.entry[name]
      else:
        self.entry[name] = txt
    self.okCallback(self.entry)

  def discard(self, *args):
    self.entry = None
    self._set_w(urwid.SolidFill())
    self.fields = None
    self.content = None
    self.lb = None
    self.cancel()

  def keypress(self, size, key):
    ret = super(passwordForm, self).keypress(size, key)
    if ret is not None:
      # FIXME: generalise these. Tab not handled ideally:
      if key in ['j', 'tab']: return self.keypress(size, 'down')
      if key in ['k', 'shift tab']: return self.keypress(size, 'up')
      if key == 'h': return self.keypress(size, 'left')
      if key == 'l': return self.keypress(size, 'right')
      if key == 'enter' and self._w.get_focus()[0] == self.newfield: self.add_new_field()
    return ret

  def _update(self):
    self.lb = urwid.ListBox(self.content)
    self._set_w(self.lb)

class koshUI(widgets.keymapwid, urwid.WidgetWrap):
  keymap = {
      'n': 'new' # FIXME: Not when button selected, etc
      }

  def __init__(self, db):
    self.db = weakref.proxy(db)
    self.pwEntry = passwordForm()
    self.pwList = passwordList(self.db, self.pwEntry, self)
    self.container = widgets.LineColumns( [
      ('weight', 0.75, self.pwList),
      self.pwEntry
      ] )
    self.vi = widgets.viCommandBar(self.container, search_function=self.pwList.search)
    urwid.WidgetWrap.__init__(self, self.vi)
  
  def new(self, size, key):
    import koshdb # FIXME: decouple this
    entry = koshdb.koshdb.passEntry(self.db._masterKeys[0])
    entry['Username'] = ''
    entry['Password'] = ''
    entry['URL'] = ''
    entry['Notes'] = '' # FIXME: Multi-line
    self.container.set_focus(self.pwEntry)
    self.pwEntry.edit(entry, self.commitNew, self.cancel)

  def commitNew(self, entry):
    self.db[entry.name] = entry
    self.pwEntry.show(entry)
    self.pwList.refresh()
    self.db.write()

  def cancel(self):
    # Necessary to get focus back
    self.container.set_focus(0)
    
  def status(self, status):
    return self.vi.update_status(status)

  def showModal(self, parent=None):
    self.mainloop = urwid.MainLoop(self)
    self.mainloop.run()
