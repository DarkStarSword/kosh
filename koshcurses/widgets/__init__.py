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
import utf8

from viCommandBar import viCommandBar

class keymapwid(object):
  keymap = {}
  def keypress(self, size, key):
    ret = super(keymapwid, self).keypress(size, key)
    if ret is None: # Sibling class handled
      return
    if key in self.keymap:
      getattr(self, self.keymap[key])(size, key)
    return key

class koshEdit(urwid.Edit):
  """ Subclass of urwid.Edit to handle ^u to kill line """
  def keypress(self, size, key):
    if key == 'ctrl u':
      self.set_edit_text('')
    else:
      return urwid.Edit.keypress(self, size, key)

class passwordEdit(keymapwid, koshEdit):
  keymap = {
      'f8': 'toggleReveal',
      'ctrl r': 'toggleReveal',
      'ctrl g': 'generate_password', # FIXME HACK: This isn't the right place for this
      }
  def __init__(self, caption="", edit_text="", multiline=False,
          align=urwid.LEFT, wrap=urwid.CLIP, allow_tab=False,
          edit_pos=None, layout=None, revealable=False, reveal=False):
    """ Force disabling wrapping as that could give away hints as to whitespace in a passphrase """
    self.revealable = revealable
    self.reveal = reveal
    koshEdit.__init__(self,caption,edit_text,multiline,align,urwid.CLIP,allow_tab,edit_pos,layout)

  def get_text(self):
    """get_text() -> text, attributes

    text -- complete text of caption and asterisks in place of edit_text
    attributes -- run length encoded attributes for text
    """
    if self.reveal:
      return super(passwordEdit, self).get_text()
    return self._caption + '*'*len(self._edit_text), self._attrib

  def toggleReveal(self, size, key):
    if not self.revealable: return key
    self.reveal = not self.reveal
    self._invalidate()

  def generate_password(self, size, key):
    import subprocess
    # HACK: Multiple tools available, allow user to select, or fall back on
    # default built in
    try:
      passwd = subprocess.check_output('pwgen -nc 12'.split()).strip()
    except subprocess.CalledProcessError:
      # FIXME: I don't have the ui here and can't notify, but this is the wrong
      # place to do this anyway, just a hack
      return
    self.set_edit_text(passwd)

class LineColumns(urwid.WidgetWrap):
  vline = urwid.SolidFill(utf8.symbol('BOX DRAWINGS LIGHT VERTICAL'))
  hline = ('flow', urwid.Divider(utf8.symbol('BOX DRAWINGS LIGHT HORIZONTAL')))
  tlcorner = ('flow', urwid.Text(utf8.symbol('BOX DRAWINGS LIGHT DOWN AND RIGHT')))
  trcorner = ('flow', urwid.Text(utf8.symbol('BOX DRAWINGS LIGHT DOWN AND LEFT')))
  blcorner = ('flow', urwid.Text(utf8.symbol('BOX DRAWINGS LIGHT UP AND RIGHT')))
  brcorner = ('flow', urwid.Text(utf8.symbol('BOX DRAWINGS LIGHT UP AND LEFT')))
  tdivisor = ('flow', urwid.Text(utf8.symbol('BOX DRAWINGS LIGHT DOWN AND HORIZONTAL')))
  bdivisor = ('flow', urwid.Text(utf8.symbol('BOX DRAWINGS LIGHT UP AND HORIZONTAL')))
  left    = ('fixed', 1, urwid.Pile( [ tlcorner, vline, blcorner ], 1))
  right   = ('fixed', 1, urwid.Pile( [ trcorner, vline, brcorner ], 1))
  divider = ('fixed', 1, urwid.Pile( [ tdivisor, vline, bdivisor ], 1))

  def __init__(self, widget_list, dividechars=0):
    def extractsize(widget):
      if type(widget) == type(()):
        return widget[:2] + tuple([urwid.Pile( [self.hline, widget[2], self.hline], 1)])
      return urwid.Pile( [self.hline, widget, self.hline], 1)
    self.widget_list = widget_list
    self.columns = urwid.Columns( [self.left] +
        reduce(lambda a,b: a+b, [[extractsize(col), self.divider] for col in widget_list])[:-1] +
        [self.right] )
    urwid.WidgetWrap.__init__(self, self.columns)

  def set_focus(self, item):
    if type(item) == type(0):
      position = item
    else:
      position = self.widget_list.index(item)
    return self.columns.set_focus(position*2 + 1)
