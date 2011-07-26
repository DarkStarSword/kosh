#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab

import urwid
import weakref
import widgets
import time

class passwordList(widgets.keymapwid, urwid.WidgetWrap):
  keymap = {
      'f5': 'showOlder',
      'ctrl p': 'showOlder',
      'f6': 'showNewer',
      'ctrl n': 'showNewer',
      'y': 'yank',
      'e': 'edit',
      'D': 'delete',
      }

  def __init__(self, db, pwForm, ui):
    self.db = db
    self.pwForm = pwForm
    self.ui = ui
    self.visibleEntries = self.db.keys()
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
      try:
        self.showing = self.db[self.lb.get_focus()[0].get_label()]
      except KeyError:
        return self.search(None)
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
    xclipboard.sendViaClipboard(self.showing.clipIter(), self.showing.name, ui=self.ui)

  def edit(self, size, key):
    self.pwForm.edit(self.showing.clone(), self.ui.commitNew, self.ui.cancel)

  def delete(self, size, key):
    del self.db[self.showing]
    self.showing = None
    self.refresh()
    self.db.write()

  def search(self, search):
    import string
    if not search:
      self.visibleEntries = self.db.keys()
      ret = None
    else:
      self.visibleEntries = []
      for entry in self.db:
        # FIXME: Don't (optionally?) search on other protected fields
        if reduce(lambda x,y: x or search.lower() in y, map(string.lower,
          [entry]+[v for (k,v) in self.db[entry].items()
            if k.lower() not in ['password']]), False):
            self.visibleEntries.append(entry)
      ret = len(self.visibleEntries)
    self.refresh()
    return ret

class passwordForm(widgets.keymapwid, urwid.WidgetWrap):
  keymap = {
      'y': 'yank',
      'S': 'runscript',
      }

  def __init__(self, ui):
    urwid.WidgetWrap.__init__(self, urwid.SolidFill())
    self.lb = None
    self.ui = ui

  def showNone(self):
    self.entry = None
    self._set_w(urwid.SolidFill())
    self.fields = None
    self.content = None
    self.lb = None

  def show(self, entry):
    if entry is None:
      return self.showNone()
    self.entry = entry
    self.content = [urwid.Text('Name: ' + self.entry.name)] + \
      [ urwid.Button(x, self.reveal_field) for x in entry ] + \
      [ urwid.Divider(), urwid.Text('Timestamp: ' + time.asctime(time.localtime(entry.timestamp()))) ]
    self._update()

  def reveal(self, entry):
    self.entry = entry
    self.content = [urwid.Text('Name: ' + self.entry.name)] + \
      [ urwid.Text(x+": " + entry[x]) for x in entry ] + \
      [ urwid.Divider(), urwid.Text('Timestamp: ' + time.asctime(time.localtime(entry.timestamp()))) ]
    self._update()

  def reveal_field(self, button):
    label = button.get_label()
    index = self.content.index(button)
    self.content = self.content[:index] + \
        [ urwid.Text(label+": " + self.entry[label]) ] + \
        self.content[index+1:]
    self._update()

  def edit(self, entry, ok, cancel):
    self.entry = entry
    self.cancel = cancel
    self.okCallback=ok
    self.fname = widgets.koshEdit('Name: ', self.entry.name)
    self.fields = [ widgets.passwordEdit(x+": ", entry[x], revealable=True) for x in entry ]
    self.newfield = widgets.koshEdit('Add new field: ')
    self.record_http_script = widgets.koshEdit('Record HTTP password change script: ')
    self._edit()
    self._update()
  def _edit(self):
    self.content = [self.fname] + self.fields + [urwid.Divider(), self.newfield,
        self.record_http_script] + [ urwid.GridFlow(
          [urwid.Button('Save', self.commit),
            urwid.Button('Cancel', self.discard) ],
          10, 3, 1, 'center')
      ]

  def add_new_field(self):
    field = self.newfield.get_edit_text().strip()
    if not field: return
    if field in self.entry: return
    self.entry[field] = ''
    self.fields += [ widgets.passwordEdit(field+': ', '', revealable=True) ]
    self._edit()
    self._update()
    #self._w.set_focus(self.newfield)

  def do_record_http_script(self):
    field = 'HACK_HTTP-SCRIPT_'+self.record_http_script.get_edit_text().strip()
    if not field: return
    import httppasswd
    # FIXME: should fetch up to date stuff from editing
    if 'Username' in self.entry:
      username = self.entry['Username']
    elif 'login' in self.entry:
      username = self.entry['login']
    if 'Password' in self.entry:
      newpass = self.entry['Password']
    elif 'passwd' in self.entry:
      newpass = self.entry['passwd']
    # FIXME: Should walk list to find this
    oldpass = self.entry['OldPassword']
    import other_ui.ui_tty as ui
    old = ui.reset()
    try:
      script = httppasswd.main(ui(), None, username, oldpass, newpass)
    finally:
      ui.restore(old)
    for f in self.fields:
      # It would be nice to just update self.entry, but we need to avoid clobbering edits...
      # If we already have a field with this name, it counts as an edit - replace the old field
      name = f.caption[:-2]
      if name == field:
        self.fields.remove(f)
    self.fields += [ widgets.passwordEdit(field+': ', script, revealable=True) ]
    self._edit()
    self._update()
  def do_play_http_script(self):
    import httppasswd
    username = self.entry['Username']
    newpass = self.entry['Password']
    # FIXME: Should walk list to find this
    oldpass = self.entry['OldPassword']
    script = self.entry[self._w.get_focus()[0].get_label()]
    import other_ui.ui_tty as ui
    import time
    old = ui.reset()
    try:
      httppasswd.main(ui(), script, username, oldpass, newpass)
      time.sleep(5)
    finally:
      time.sleep(5)
      ui.restore(old)

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
    self.showNone()
    self.cancel()

  def keypress(self, size, key):
    focus = self._w.get_focus()[0]
    ret = super(passwordForm, self).keypress(size, key)
    if ret is not None:
      # FIXME: generalise these. Tab not handled ideally:
      if key in ['j', 'tab']: return self.keypress(size, 'down')
      if key in ['k', 'shift tab']: return self.keypress(size, 'up')
      if key == 'h': return self.keypress(size, 'left')
      if key == 'l': return self.keypress(size, 'right')
      if key == 'enter':
        if focus == self.newfield: self.add_new_field()
        if focus == self.record_http_script: self.do_record_http_script()
    return ret

  def yank(self, size, key):
    label = self._w.get_focus()[0].get_label()
    import xclipboard
    xclipboard.sendViaClipboard([(label, self.entry[label])], self.entry.name, ui=self.ui)

  def runscript(self, size, key):
    label = self._w.get_focus()[0].get_label()
    if not label.startswith('HACK_HTTP-SCRIPT_'):
      self.ui.status("Selected field is not a script");
      return None
    try:
      self.do_play_http_script()
    except:
      self.ui.status("Exception while running HTTP password changing script");
    return None

  def _update(self):
    self.lb = urwid.ListBox(self.content)
    self._set_w(self.lb)

class koshUI(widgets.keymapwid, urwid.WidgetWrap):
  keymap = {
      'n': 'new' # FIXME: Not when button selected, etc
      }

  def __init__(self, db):
    self.db = weakref.proxy(db)
    self.pwEntry = passwordForm(self)
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
    self.db.write()
    self.pwList.refresh()

  def cancel(self):
    # Necessary to get focus back
    self.container.set_focus(0)
    
  def status(self, status, append=False):
    return self.vi.update_status(status, append)

  def showModal(self, parent=None):
    self.mainloop = urwid.MainLoop(self)
    self.mainloop.run()
