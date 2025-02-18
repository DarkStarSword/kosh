#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab:sts=2

# Copyright (C) 2009-2025 Ian Munsie
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

import urwid
import weakref
from . import widgets, dialog
import time
import sys
from functools import reduce
import version
import otpauth

class passwordList(widgets.keymapwid, urwid.WidgetWrap):
  keymap = {
      'f5': 'showOlder',
      'ctrl p': 'showOlder',
      'f6': 'showNewer',
      'ctrl n': 'showNewer',
      'g': 'goto',
      'y': 'yank',
      'Y': 'capital_yank',
      'e': 'edit',
      'D': 'delete',
      }

  def __init__(self, db, pwForm, ui):
    self.db = db
    self.pwForm = pwForm
    self.ui = ui
    self.showing = None
    self.visibleEntries = list(self.db.keys())
    self.refresh()
    urwid.WidgetWrap.__init__(self, self.lb)

  def expire(self):
    self.db = {}
    self.showing = None
    self.visibleEntries = []
    self.refresh()

  def refresh(self, focus_entry=None):
    if focus_entry is not None and focus_entry not in self.visibleEntries:
      self.search(None)
    self.visibleEntries.sort(key = lambda x: x.lower())
    self.content = [ urwid.Button(x, self.select) for x in self.visibleEntries ]
    self.lb = urwid.ListBox(self.content)
    self.selection = 0
    self._set_w(self.lb)
    if len(self.visibleEntries):
      try:
        if focus_entry:
          self.showing = self.db[focus_entry]
          self.lb.set_focus(self.visibleEntries.index(focus_entry))
          self.ui.container.set_focus(0)
        else:
          self.showing = self.db[self.lb.get_focus()[0].get_label()]
      except KeyError:
        return self.search(None)
      self.pwForm.show(self.showing)

  def keypress(self, size, key):
    self.ui.touch()
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
    self.ui.touch()
    showing = self.db[button.get_label()]
    if self.showing in showing.history():
      # Either pressed enter, or clicked a second time on same entry
      if not self.pwForm.all_revealed:
        self.pwForm.reveal_all(self.showing)
      else:
        self.pwForm.hide_all(self.showing)
    else:
      # May happen due to mouse click
      self.showing = showing
      self.pwForm.show(self.showing)
    # FIXME: focus

  def showOlder(self, size, key):
    if not self.showing:
      self.ui.status("No entry selected");
      return
    if self.showing.older is not None:
      self.showing = self.showing.older
      self.pwForm.show(self.showing)

  def showNewer(self, size, key):
    if not self.showing:
      self.ui.status("No entry selected");
      return
    if self.showing.newer is not None:
      self.showing = self.showing.newer
      self.pwForm.show(self.showing)

  def goto(self, size, key):
    if not self.showing:
      self.ui.status("No entry selected");
      return
    def launch(url):
      import subprocess
      try:
        self.ui.status("Going to %s" % url)
        subprocess.check_call(['sensible-browser', url]) # FIXME HACK: Debian specific, have a setting and try to detect default
      except subprocess.CalledProcessError as e:
        self.ui.status("Exception calling web browser: %s" % str(e));
    import threading

    # TODO: Refactor this into a geturl() function in the db & check metadata for URL type fields
    if 'URL' in self.showing:
      url = self.showing['URL']
    elif 'url' in self.showing:
      url = self.showing['URL']
    else:
      self.ui.status("No URL in password record");
      return

    t = threading.Thread(target=launch, args=[url])
    t.daemon = True
    t.start()

  def yank(self, size, key):
    if not self.showing:
      self.ui.status("No entry selected");
      return
    if self.ui.clipboard:
      blobs = otpauth.totp_iter(self.showing.clipIter())
      self.ui.clipboard.sendViaClipboard(blobs, self.showing.name, ui=self.ui)
    else:
      self.ui.status("Clipboard support unavailable");

  def capital_yank(self, size, key):
    if not self.showing:
      self.ui.status("No entry selected");
      return
    if self.ui.clipboard:
      blobs = otpauth.totp_iter(self.showing.clipIter())
      self.ui.clipboard.sendViaClipboardSimple(blobs, self.showing.name, ui=self.ui)
    else:
      self.ui.status("Clipboard support unavailable");

  def edit(self, size, key):
    if not self.showing:
      self.ui.status("No entry selected");
      return
    self.ui.container.set_focus(self.pwForm)
    self.pwForm.edit(self.showing.clone(), self.ui.commitNew, self.ui.cancel)

  def selectable(self):
    return not self.pwForm.editing

  def delete(self, size, key):
    if not self.showing:
      self.ui.status("No entry selected");
      return
    del self.db[self.showing]
    self.showing = None
    self.refresh()
    self.db.write()

  def search(self, search):
    if not search:
      self.visibleEntries = list(self.db.keys())
      ret = None
    else:
      self.visibleEntries = []
      for entry in self.db:
        # FIXME: Don't (optionally?) search on other protected fields
        if reduce(lambda x,y: x or search.lower() in y, list(map(str.lower,
          [entry]+[v for (k,v) in list(self.db[entry].items())
            if k.lower() not in ['password']])), False):
            self.visibleEntries.append(entry)
      ret = len(self.visibleEntries)
    self.refresh()
    return ret

class passwordForm(widgets.keymapwid, urwid.WidgetWrap):
  keymap = {
      'y': 'yank',
      'Y': 'capital_yank',
      'S': 'runscript',
      }

  def __init__(self, ui):
    urwid.WidgetWrap.__init__(self, urwid.SolidFill())
    self.lb = None
    self.ui = ui
    self.editing = False
    self.all_revealed = False
    self.content = None

  def showNone(self):
    if self.editing:
      return
    self.entry = None
    self._set_w(urwid.SolidFill())
    self.fields = None
    self.content = None
    self.lb = None
    self.all_revealed = False

  def show(self, entry):
    if self.editing:
      return
    if entry is None:
      return self.showNone()
    self.entry = entry
    self.content = [urwid.Text('Name: ' + self.entry.name)] + \
      [ self.make_unrevealed_widget(x) for x in entry ] + \
      [ urwid.Divider(), urwid.Text('Timestamp: ' + time.asctime(time.localtime(entry.timestamp()))) ]
    self.all_revealed = False
    self._update()

  def make_unrevealed_widget(self, entry):
    widget = urwid.Button(entry, self.reveal_field)
    widget.kosh_entry = entry
    return widget

  def make_revealed_widget(self, entry):
    val = self.entry[entry]
    totp = otpauth.try_totp(val)
    if totp is not None:
      widget = widgets.RevealedTOTPWidget(entry, totp, self.hide_field)
    else:
      widget = urwid.Button(entry+": " + val, self.hide_field)
    widget.kosh_entry = entry
    return widget

  def reveal_all(self, entry):
    if self.editing:
      return
    self.entry = entry
    self.content = [urwid.Text('Name: ' + self.entry.name)] + \
      [ self.make_revealed_widget(x) for x in entry ] + \
      [ urwid.Divider(), urwid.Text('Timestamp: ' + time.asctime(time.localtime(entry.timestamp()))) ]
    self._update()
    self.all_revealed = True

  def hide_all(self, entry):
    if self.editing:
      return
    self.entry = entry
    self.content = [urwid.Text('Name: ' + self.entry.name)] + \
      [ self.make_unrevealed_widget(x) for x in entry ] + \
      [ urwid.Divider(), urwid.Text('Timestamp: ' + time.asctime(time.localtime(entry.timestamp()))) ]
    self._update()
    self.all_revealed = False

  def reveal_field(self, button):
    self.ui.touch()
    if self.editing:
      return
    tag = button.kosh_entry
    index = self.content.index(button)
    self.content = self.content[:index] + \
        [ self.make_revealed_widget(tag) ] + \
        self.content[index+1:]
    self._update()
    self._w.set_focus(index)

  def hide_field(self, button):
    self.ui.touch()
    if self.editing:
      return
    tag = button.kosh_entry
    index = self.content.index(button)
    self.content = self.content[:index] + \
        [ self.make_unrevealed_widget(tag) ] + \
        self.content[index+1:]
    self._update()
    self._w.set_focus(index)

  def edit(self, entry, ok, cancel):
    self.editing = True
    self.entry = entry
    self.cancel = cancel
    self.okCallback=ok
    self.fname = widgets.koshEdit('Name: ', self.entry.name)
    self.fields = [ widgets.passwordEdit(x+": ", entry[x], revealable=True) for x in entry ]
    self.newfield = widgets.koshEdit('Add new field: ')
    self.record_http_script = widgets.koshEdit('Record HTTP password change script: ')
    self.edit_clip_order = urwid.CheckBox('Edit clipboard order', 'CopyFieldOrder' in entry.meta)
    urwid.connect_signal(self.edit_clip_order, 'postchange', self.on_edit_clip_order_change)
    self._edit()
    self._update()
  def _edit(self):
    rows = self.fields
    if self.edit_clip_order.get_state():
      # Since a number of functions alter self.fields to e.g. add/modify/remove
      # fields on the fly, generate the second column for clip order live
      # whenever this is called, creating and caching the clip order widgets in a
      # custom attribute on the password edit widgets as needed
      rows = [ urwid.Columns([
        ('weight', 1.0, field),
        (3, self.get_clip_order_widget(field))
      ]) for field in self.fields]

    self.content = [self.fname] + rows + [urwid.Divider(), self.newfield,
        self.record_http_script, self.edit_clip_order] + [ urwid.GridFlow(
          [urwid.Button('Save', self.commit),
            urwid.Button('Cancel', self.discard) ],
          10, 3, 1, 'center')
      ]

  def get_clip_order_widget(self, field):
    '''
    Gets the clip order widget associated with a passwordEdit widget
    '''
    if not hasattr(field, 'kosh_cliporder_widget'):
      val = ''
      name = field.caption[:-2] # FIXME: Store in custom attribute
      if 'CopyFieldOrder' in self.entry.meta and name in self.entry.meta['CopyFieldOrder']:
        val = self.entry.meta['CopyFieldOrder'].index(name)
      field.kosh_cliporder_widget = urwid.IntEdit('|', val)
    return field.kosh_cliporder_widget

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
      name = f.caption[:-2] # FIXME: Store in custom attribute
      if name == field:
        self.fields.remove(f)
    self.fields += [ widgets.passwordEdit(field+': ', script, revealable=True) ]
    self._edit()
    self._update()

  def on_edit_clip_order_change(self, checkbox, new_state):
    self._edit()
    self._update()

  def save_ui(fn):
    def _save_ui(*args, **kwargs):
      import other_ui.ui_tty as ui
      import time
      old = ui.reset()
      try:
        fn(*args, ui=ui, **kwargs)
        time.sleep(5)
      finally:
        time.sleep(5)
        ui.restore(old)
    return _save_ui

  def password_change_script(fn):
    def wrap(self, *args, **kwargs):
      username = self.entry['Username']
      newpass = self.entry['Password']
      # FIXME: Should walk list to find this
      oldpass = self.entry['OldPassword']
      value = self.entry[self._w.get_focus()[0].kosh_entry]
      return fn(self, *args, username=username, newpass=newpass, oldpass=oldpass, value=value, **kwargs)
    return wrap

  @save_ui
  @password_change_script
  def do_play_http_script(self, username, newpass, oldpass, value, ui):
    import httppasswd
    httppasswd.main(ui(), value, username, oldpass, newpass)

  @save_ui
  @password_change_script
  def change_local_password(self, username, newpass, oldpass, value, ui):
    import sshpasswd
    sshpasswd.change_local(ui(), oldpass, newpass)

  @save_ui
  @password_change_script
  def do_ssh_password_change(self, username, newpass, oldpass, value, ui):
    import sshpasswd
    if '@' in value:
      (username, value) = value.split('@', 1)
    sshpasswd.change_ssh(ui(), value, username, oldpass, newpass)

  @save_ui
  @password_change_script
  def do_update_conf_password(self, username, newpass, oldpass, value, ui):
    import sshpasswd
    import os
    sshpasswd.change_conf(ui(), os.path.expanduser(value), oldpass, newpass)

  def validate(self):
    return self.fname.get_edit_text() != ''

  def commit(self, *args):
    if not self.validate():
      # FIXME: Notify
      return

    copy_field_order = None
    if self.edit_clip_order.get_state():
      copy_field_order = []
    elif 'CopyFieldOrder' in self.entry.meta:
      del self.entry.meta['CopyFieldOrder']

    self.entry.name = self.fname.get_edit_text()
    for field in self.fields:
      name = field.caption[:-2] # FIXME: Store in custom attribute
      txt = field.get_edit_text()
      if txt != '':
        self.entry[name] = txt
        if copy_field_order is not None:
          clip_order = self.get_clip_order_widget(field).get_edit_text()
          if clip_order != '':
            copy_field_order.append((int(clip_order), name))
      elif name in self.entry:
        del self.entry[name]

    if copy_field_order is not None:
      self.entry.meta['CopyFieldOrder'] = list(zip(*sorted(copy_field_order)))[1]

    self.editing = False
    self.okCallback(self.entry)

  def discard(self, *args):
    message = 'Really discard changes?'
    dlg = dialog.YesNoDialog(message=message)
    self.ui.mainloop.stop()
    response = dlg.showModal()
    self.ui.mainloop.start()
    if response:
      cancelled_entry = self.entry.name
      self.editing = False
      self.showNone()
      self.cancel(cancelled_entry)

  def keypress(self, size, key):
    self.ui.touch()
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
    if self.ui.clipboard:
      label = self._w.get_focus()[0].kosh_entry
      blob = otpauth.try_totp_str(self.entry[label])
      self.ui.clipboard.sendViaClipboard([(label, blob)], self.entry.name, ui=self.ui)
    else:
      self.ui.status("Clipboard support unavailable");

  def capital_yank(self, size, key):
    if self.ui.clipboard:
      label = self._w.get_focus()[0].kosh_entry
      blob = otpauth.try_totp_str(self.entry[label])
      self.ui.clipboard.sendViaClipboardSimple([(label, blob)], self.entry.name, ui=self.ui)
    else:
      self.ui.status("Clipboard support unavailable");

  def runscript(self, size, key):
    if self.editing:
      # Added to avoid exception if accidentally type S on Save/Cancel buttons
      # while editing. Currently can't run a script in edit mode anyway, so
      # just disallow.
      return
    try:
      label = self._w.get_focus()[0].kosh_entry
      if label.startswith('HACK_HTTP-SCRIPT_'):
        self.do_play_http_script()
      elif label.startswith('HACK_LOCALHOST'):
        self.change_local_password()
      elif label.startswith('HACK_SSH_'):
        self.do_ssh_password_change()
      elif label.startswith('HACK_CONF_'):
        self.do_update_conf_password()
      else:
        self.ui.status("Selected field is not a supported password changing script");
        return None
    except Exception as e:
      # FIXME: Print traceback, this status message might get overridden by "matched n entries"
      self.ui.status("%s while running password changing script: %s" % (e.__class__.__name__, str(e)));

  def _update(self):
    self.lb = urwid.ListBox(self.content)
    self._set_w(self.lb)

  def tick(self):
    if self.content:
      for widget in self.content:
        if isinstance(widget, widgets.RevealedTOTPWidget):
          widget.tick()

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
    self.touch()
    self.init_clipboard()

  def touch(self):
    if not hasattr(self, 'expire') or self.expire >= time.time() or self.vi.variables['pause']:
      self.expire = time.time() + 60
    self.update_countdown_display()

  def update_countdown_display(self):
    import math

    if self.vi.variables['pause']:
      if self.vi.get_status_right() == 'PAUSE':
        self.vi.update_status_right('!*!*!')
      else:
        self.vi.update_status_right('PAUSE')
      return

    remaining = math.ceil(self.expire - time.time())
    if remaining < 0:
      if not self.pwEntry.editing:
        raise urwid.ExitMainLoop()
      # Currently editing an entry - defer closing until the user has saved or
      # cancelled to avoid losing their entry, but prevent access to any other
      # entry incase they left the program open by mistake
      self.vi.update_status_right({
        1: ' :  ',
        0: '0:00',
      }[remaining % 2])
      if self.pwList:
        self.pwList.expire()
        self.pwList = None
        self.container.set_widget(0, ('weight', 0.75, urwid.Filler(urwid.Text('Locked', 'center'))))
    else:
      self.vi.update_status_right('%d:%02d' % (remaining // 60, remaining % 60))
    try:
      self.mainloop.draw_screen()
    except: pass

  def tick(self, mainloop=None, user_data=None):
    self.update_countdown_display()
    self.pwEntry.tick()
    self.alarm = self.mainloop.set_alarm_at(time.time() + 1, self.tick)

  def new(self, size, key):
    if self.pwEntry.editing:
      return
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
    if self.pwList:
      self.pwList.refresh(entry.name)

  def cancel(self, cancelled_entry):
    # Necessary to get focus back
    self.container.set_focus(0)
    if self.pwList and cancelled_entry:
      #self.pwList.refresh(self.pwList.showing.name)
      self.pwList.refresh(cancelled_entry)

  def status(self, status, append=False):
    return self.vi.update_status(status, append)

  def showModal(self, parent=None):
    self.mainloop = urwid.MainLoop(self)
    self.tick()
    while True:
      try:
        self.mainloop.run()
        break
      except KeyboardInterrupt:
        if not self.pwEntry.editing:
          raise
        message = 'Currently editing a password record\nReally exit without saving?'
        dlg = dialog.YesNoDialog(message=message)
        while True:
          try:
            response = dlg.showModal()
            break
          except KeyboardInterrupt:
            # In case of accidental double ctrl+c ask again
            continue
        if response:
          raise
        continue

  def init_clipboard(self):
    try:
      if sys.platform in ('win32', 'cygwin'):
        import winclipboard as clipboard
      elif version.is_wsl():
        import wslclipboard as clipboard
        clipboard.init(self)
      elif sys.platform == 'darwin':
        import macclipboard as clipboard
      elif version.HAS_TERMUX_API:
        import termuxclipboard as clipboard
      else:
        import xclipboard as clipboard
    except Exception as e:
      self.ui.status("Error intialising clipboard support: %s" % str(e));
      clipboard = None
    self.clipboard = clipboard

