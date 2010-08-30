#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab

import urwid
import widgets

class inputDialog(urwid.WidgetWrap):
  def __init__(self, caption='', txt='', message=None, width=0):
    #self.edit = urwid.Edit(caption+': ', txt)
    self.edit = widgets.passwordEdit(caption+': ', txt)
    listboxcontent = [
      urwid.Text(message, align='center'),
      urwid.Divider('-'),
      self.edit
    ]
    listbox = urwid.ListBox(listboxcontent)
    self.width = reduce(lambda m,s: max(len(s),m), message.split('\n'), 0) + 6
    self.height = message.count('\n') + len(listboxcontent) + 2
    if self.width < width:
      self.width = width
    urwid.WidgetWrap.__init__(self, urwid.LineBox(listbox))

  def showModal(self, parent=None):
    if parent is None:
      parent = urwid.SolidFill()
    overlay = urwid.Overlay(self, parent, 'center', ('relative', self.width), 'middle', self.height)
    def exit_on_input(input):
      if input.lower() in ('enter'):
        raise urwid.ExitMainLoop()
    urwid.MainLoop(overlay, unhandled_input=exit_on_input).run()
    return self.edit.get_edit_text()

if __name__=='__main__':
  d = inputDialog(message='Enter master password:', width=30)
  print d.showModal()
