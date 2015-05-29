#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab

# Copyright (C) 2009-2015 Ian Munsie
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
    overlay = urwid.Overlay(self, parent, 'center', self.width, 'middle', self.height)
    def exit_on_input(input):
      if input in ['enter']:
        raise urwid.ExitMainLoop()
    urwid.MainLoop(overlay, unhandled_input=exit_on_input).run()
    return self.edit.get_edit_text()

if __name__=='__main__':
  d = inputDialog(message='Enter master password:', width=30)
  print d.showModal()
