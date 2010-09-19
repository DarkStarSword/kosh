#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab

import urwid
import weakref
import widgets

class passwordList(urwid.WidgetWrap):
  def __init__(self, db):
    self.content = [ urwid.Button(x, self.select) for x in db ]
    lb = urwid.ListBox(self.content)
    urwid.WidgetWrap.__init__(self, lb)

  def keypress(self, size, key):
    if key == 'j' or key == 'k':
      self.content.append(urwid.Text(key))
      return
    return super(passwordList, self).keypress(size, key)

  def select(self, button):
    pass

class passwordForm(urwid.WidgetWrap):
  def __init__(self):
    urwid.WidgetWrap.__init__(self, urwid.SolidFill())
    self.lb = None
    self.editing = False

  def show(self, entry):
    self.entry = entry
    self.content = [urwid.Text('Name:'), urwid.Text(self.entry.name)]
    self._update()

  def edit(self, entry):
    self.entry = entry
    self.content = [urwid.Edit('Name: ', self.entry.name)] + \
      [ urwid.Edit(x+": ", entry[x]) for x in entry ] + \
      [ urwid.GridFlow(
          [urwid.Button('Save'), urwid.Button('Cancel') ],
          10, 3, 1, 'center')
      ]
    self.editing = True
    self._update()

  def keypress(self, size, key):
    if self.lb is None:
      return super(passwordForm, self).keypress(size, key)
    if key == 'tab': # FIXME: I'm certain there is a better way to do this
      focus_widget, position = self.lb.get_focus()
      self.lb.set_focus(position+1)
      return
    if key == 'shift tab':
      focus_widget, position = self.lb.get_focus()
      position = position-1
      if position >= 0:
        self.lb.set_focus(position)
      return
    return super(passwordForm, self).keypress(size, key)

  def _update(self):
    self.lb = urwid.ListBox(self.content)
    self._set_w(self.lb)

class koshUI(widgets.keymapwid, urwid.WidgetWrap):
  keymap = {
      'n': 'new'
      }

  def __init__(self, db):
    self.db = weakref.proxy(db)
    self.pwList = passwordList(self.db)
    self.pwEntry = passwordForm()
    self.container = widgets.LineColumns( [
      ('weight', 0.75, self.pwList),
      self.pwEntry
      ] )
    urwid.WidgetWrap.__init__(self, self.container)
  
  def new(self, size, key):
    import koshdb # FIXME: decouple this
    entry = koshdb.koshdb.passEntry(self.db._masterKeys[0])
    entry['Username'] = ''
    entry['Password'] = ''
    entry['URL'] = ''
    entry['Notes'] = '' # FIXME: Multi-line
    self.container.set_focus(self.pwEntry)
    self.pwEntry.edit(entry)

  def showModal(self, parent=None):
    def exit_on_input(input):
      if input.lower() in ('escape'):
        raise urwid.ExitMainLoop()
    urwid.MainLoop(self, unhandled_input=exit_on_input).run()
