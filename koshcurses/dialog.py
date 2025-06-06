#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab

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
import io
from . import widgets
from functools import reduce

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

class YesNoDialog(urwid.WidgetWrap):
  def __init__(self, message=None, width=0):
    columncontent = [
      urwid.Button('No', self.on_press, False),
      urwid.Button('Yes', self.on_press, True),
    ]
    listboxcontent = [
      urwid.Text(message, align='center'),
      urwid.Divider('-'),
      urwid.Columns(columncontent, 5),
    ]
    listbox = urwid.ListBox(listboxcontent)
    self.width = reduce(lambda m,s: max(len(s),m), message.split('\n'), 0) + 6
    self.height = message.count('\n') + len(listboxcontent) + 2
    if self.width < width:
      self.width = width
    urwid.WidgetWrap.__init__(self, urwid.LineBox(listbox))

  def on_press(self, widget, user_data):
    self.response = user_data
    raise urwid.ExitMainLoop()

  def showModal(self, parent=None):
    if parent is None:
      parent = urwid.SolidFill()
    overlay = urwid.Overlay(self, parent, 'center', self.width, 'middle', self.height)
    urwid.MainLoop(overlay).run()
    return self.response

class QRDialog(urwid.ListBox):
  def __init__(self, message=None):
    try:
      import qrcode
      qr = qrcode.QRCode(border=1)
      qr.add_data(message)
      buf = io.StringIO()
      qr.print_ascii(out=buf)
      message = buf.getvalue().rstrip('\n')
    except ImportError:
      message = "Please install python3-qrcode to export QR Codes"

    listboxcontent = [
      urwid.Text(("qrcode", message)),
      urwid.Padding(urwid.Button('OK', self.on_press), 'center', 6),
    ]
    urwid.ListBox.__init__(self, listboxcontent)
    self.width = reduce(lambda m,s: max(len(s),m), message.split('\n'), 0)
    self.height = message.count('\n') + len(listboxcontent)

  def on_press(self, widget):
    raise urwid.ExitMainLoop()

  def showModal(self, parent=None):
    # OpenCV only recognises black on white QR codes, not white on black, while
    # Android reads it either way. Since there might be others picky like that,
    # try to set the terminal palette
    palette = [
        ("qrcode", "black", "light gray"),
    ]

    if parent is None:
      parent = urwid.SolidFill()
    overlay = urwid.Overlay(self, parent, 'center', self.width, 'middle', self.height)
    urwid.MainLoop(overlay, palette).run()

if __name__=='__main__':
  d = inputDialog(message='Enter master password:', width=30)
  print(d.showModal())
