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

class KeyFileDialog(urwid.WidgetWrap):
  """
  Dialog prompting the user to locate a key file when none was found automatically.
  showModal(error=None) returns (path, remember_bool), or ('', False) if cancelled.
  The widget is reused across retries so the path field preserves what was typed.
  """
  WIDTH = 54

  def __init__(self):
    self.path_edit = widgets.koshEdit('Path: ')
    self.remember_checkbox = urwid.CheckBox('Remember in key file (r: redirect)')
    # Build a placeholder widget; real content is set in showModal
    urwid.WidgetWrap.__init__(self, urwid.SolidFill())

  def _build(self, error=None):
    message = error if error else 'No master key found.\nEnter the path to a key file:'
    content = [
      urwid.Text(message, align='center'),
      urwid.Divider('-'),
      self.path_edit,
      self.remember_checkbox,
      urwid.Divider(),
      urwid.Text('Enter to confirm  Esc to cancel', align='center'),
    ]
    height = message.count('\n') + len(content) + 2  # +2 for LineBox border
    self._w = urwid.LineBox(urwid.ListBox(content))
    return height

  def showModal(self, error=None):
    height = self._build(error)
    self.confirmed = False
    parent = urwid.SolidFill()
    overlay = urwid.Overlay(self, parent, 'center', self.WIDTH, 'middle', height)
    def exit_on_input(key):
      if key == 'enter':
        self.confirmed = True
        raise urwid.ExitMainLoop()
      elif key == 'esc':
        raise urwid.ExitMainLoop()
    urwid.MainLoop(overlay, unhandled_input=exit_on_input).run()
    if self.confirmed and self.path_edit.get_edit_text().strip():
      return (self.path_edit.get_edit_text().strip(), self.remember_checkbox.get_state())
    return ('', False)

class UnlockDialog(urwid.WidgetWrap):
  """
  Unified database unlock dialog.

  Shows one row per discovered KeySource (passphrase field or unavailable
  notice), plus an "Add key file" section at the bottom.  The dialog
  validates credentials internally via KeySource.try_unlock() and only
  closes once at least one key is successfully unlocked, or the user
  presses Esc to cancel.

  showModal() returns:
    ([(KeySource, passphrase)], [(path, remember_bool)])
      — successfully unlocked sources + any user-added file paths
  or None if the user cancelled.

  Designed to be extensible: future key types (FIDO2, etc.) just need
  a new row widget type; the validation loop is unchanged.
  """

  WIDTH = 60

  def __init__(self, key_sources, scan_key_file):
    self._scan_key_file = scan_key_file
    self._result = None        # set when dialog exits successfully
    self._cancelled = False

    self._walker = urwid.SimpleFocusListWalker([])
    listbox = urwid.ListBox(self._walker)
    urwid.WidgetWrap.__init__(self, urwid.LineBox(listbox))
    self._rebuild(key_sources)

  # ------------------------------------------------------------------
  # Widget building helpers
  # ------------------------------------------------------------------

  def _rebuild(self, key_sources):
    """(Re)build the walker contents from a list of KeySource objects."""
    rows = []
    rows.append(urwid.Text('Unlock database', align='center'))
    rows.append(urwid.Divider('-'))

    if not key_sources:
      rows.append(urwid.Text('No key sources found.', align='center'))
    else:
      for ks in key_sources:
        rows.extend(self._rows_for_source(ks))

    rows.append(urwid.Divider('-'))
    rows.extend(self._add_file_rows())
    rows.append(urwid.Divider())
    rows.append(urwid.Text('Enter to unlock  Esc to cancel', align='center'))

    self._walker[:] = rows
    # Focus first interactive widget
    for i, w in enumerate(self._walker):
      if self._is_focusable(w):
        self._walker.set_focus(i)
        break

  def _rows_for_source(self, ks):
    """Return a list of urwid widgets representing one KeySource row."""
    from koshdb.koshdb import KeySource
    if ks.source_type == KeySource.TYPE_PASSPHRASE:
      return self._passphrase_rows(ks)
    elif ks.source_type == KeySource.TYPE_UNAVAILABLE:
      return self._unavailable_rows(ks)
    # Unknown future type — show a placeholder
    return [urwid.Text('Unknown key type: %s (%s)' % (ks.source_type, ks.source_file))]

  def _passphrase_rows(self, ks):
    edit = widgets.passwordEdit('')
    edit._key_source = ks
    error_text = urwid.Text('')
    error_text._is_error = True   # marker so _set_error can find it
    ks._edit        = edit
    ks._error_widget = error_text
    return [
      urwid.Text('Passphrase for %s:' % ks.source_file),
      edit,
      error_text,
    ]

  def _unavailable_rows(self, ks):
    retry_btn = urwid.Button('Retry')
    urwid.connect_signal(retry_btn, 'click', self._on_retry, ks)
    cols = urwid.Columns([
      urwid.Text('Unavailable: %s\n  %s' % (ks.source_file, ks.error or '')),
      ('fixed', 9, retry_btn),
    ], dividechars=1)
    ks._retry_widget = cols   # keep reference so we can replace it
    return [cols]

  def _add_file_rows(self):
    self._add_path_edit = widgets.koshEdit('')
    self._add_remember  = urwid.CheckBox('Remember (add r: redirect)')
    self._add_files = []   # accumulated (path, remember) pairs
    return [
      urwid.Text('Add key file path (Enter to scan):'),
      self._add_path_edit,
      self._add_remember,
    ]

  @staticmethod
  def _is_focusable(w):
    return isinstance(w, (widgets.koshEdit, widgets.passwordEdit,
                          urwid.CheckBox, urwid.Button))

  # ------------------------------------------------------------------
  # Event handlers
  # ------------------------------------------------------------------

  def _on_retry(self, button, ks):
    """Re-scan an unavailable source; update its row on success."""
    new_sources = self._scan_key_file(ks.source_file)
    # Replace the old row widget(s) in the walker
    try:
      idx = self._walker.index(ks._retry_widget)
    except ValueError:
      return
    new_rows = []
    for ns in new_sources:
      new_rows.extend(self._rows_for_source(ns))
    self._walker[idx:idx+1] = new_rows

  def _try_add_file(self):
    """Scan the path in the add-file field and insert new source rows."""
    path = self._add_path_edit.get_edit_text().strip()
    if not path:
      return
    remember = self._add_remember.get_state()
    self._add_files.append((path, remember))
    self._add_path_edit.set_edit_text('')

    new_sources = self._scan_key_file(path)
    # Insert the new rows just before the bottom divider (3 rows from end:
    # divider, hint text) — find the second-to-last Divider
    insert_at = max(0, len(self._walker) - 3)
    new_rows = []
    for ns in new_sources:
      new_rows.extend(self._rows_for_source(ns))
    if new_rows:
      self._walker[insert_at:insert_at] = new_rows

  def _try_unlock(self):
    """
    Attempt to unlock with whatever passphrases have been filled in.
    On success, sets self._result and raises ExitMainLoop.
    On failure, annotates each failed passphrase row with an error.
    """
    from koshdb.koshdb import KeySource
    unlocked = []
    any_attempt = False

    for w in self._walker:
      if not isinstance(w, widgets.passwordEdit):
        continue
      ks = getattr(w, '_key_source', None)
      if ks is None:
        continue
      passphrase = w.get_edit_text()
      if not passphrase:
        if hasattr(ks, '_error_widget'):
          ks._error_widget.set_text('')
        continue
      any_attempt = True
      try:
        ks.try_unlock(passphrase)   # validates credential
        unlocked.append((ks, passphrase))
        if hasattr(ks, '_error_widget'):
          ks._error_widget.set_text('')
      except Exception:
        if hasattr(ks, '_error_widget'):
          ks._error_widget.set_text(('error', 'Incorrect passphrase'))

    if unlocked:
      self._result = (unlocked, self._add_files)
      raise urwid.ExitMainLoop()

    if not any_attempt:
      # No passphrase was entered at all — show a hint rather than silently doing nothing
      pass

  # ------------------------------------------------------------------
  # Input handling and modal loop
  # ------------------------------------------------------------------

  def keypress(self, size, key):
    """Route Enter and Esc; let urwid handle everything else."""
    if key == 'esc':
      self._cancelled = True
      raise urwid.ExitMainLoop()

    if key == 'enter':
      # If focus is on the add-file path field, scan it; otherwise try unlock
      focus = self._walker.get_focus()[0]
      if focus is self._add_path_edit:
        self._try_add_file()
        return
      self._try_unlock()
      return

    return super().keypress(size, key)

  def showModal(self, parent=None):
    if parent is None:
      parent = urwid.SolidFill()
    # Calculate height: content rows + 2 for LineBox border
    height = min(len(self._walker) + 2, 40)
    overlay = urwid.Overlay(self, parent, 'center', self.WIDTH,
                            'middle', height)
    palette = [('error', 'dark red', '')]
    urwid.MainLoop(overlay, palette=palette).run()
    return None if self._cancelled else self._result


if __name__=='__main__':
  d = inputDialog(message='Enter master password:', width=30)
  print(d.showModal())
