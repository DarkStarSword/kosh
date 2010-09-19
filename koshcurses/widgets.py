#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab

import urwid

class koshEdit(urwid.Edit):
  """ Subclass of urwid.Edit to handle ^u to kill line """
  def keypress(self, size, key):
    if key == 'ctrl u':
      self.set_edit_text('')
    else:
      return urwid.Edit.keypress(self, size, key)

class passwordEdit(koshEdit):
  def __init__(self, caption="", edit_text="", multiline=False,
          align=urwid.LEFT, wrap=urwid.CLIP, allow_tab=False,
          edit_pos=None, layout=None):
    """ Force disabling wrapping as that could give away hints as to whitespace in a passphrase """
    koshEdit.__init__(self,caption,edit_text,multiline,align,urwid.CLIP,allow_tab,edit_pos,layout)

  def get_text(self):
    """get_text() -> text, attributes

    text -- complete text of caption and asterisks in place of edit_text
    attributes -- run length encoded attributes for text
    """
    return self._caption + '*'*len(self._edit_text), self._attrib

class keymapwid(object):
  keymap = {}
  def keypress(self, size, key):
    if key in self.keymap:
      getattr(self, self.keymap[key])(size, key)
    else:
      # Pass keypress to sibling class:
      super(keymapwid, self).keypress(size, key)
