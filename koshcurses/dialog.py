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

class AddKeyFileDialog(urwid.WidgetWrap):
  """
  Modal dialog for loading an additional key file into the unlock dialog.
  showModal() returns (path, remember_bool) or None if cancelled.
  """
  WIDTH = 58

  def __init__(self, redir_key_name='redir.key'):
    self._result = None
    self.path_edit = widgets.koshEdit('Path: ')
    self.remember_checkbox = urwid.CheckBox('Save path to %s' % redir_key_name)
    load_btn   = urwid.Button('Load',   self._on_load)
    cancel_btn = urwid.Button('Cancel', self._on_cancel)
    content = [
      urwid.Text('Load additional key file', align='center'),
      urwid.Divider('-'),
      self.path_edit,
      self.remember_checkbox,
      urwid.Divider('-'),
      urwid.Columns([
        urwid.Padding(load_btn,   'center', 8),
        urwid.Padding(cancel_btn, 'center', 10),
      ]),
    ]
    self._height = len(content) + 2  # +2 for LineBox border
    walker = urwid.SimpleFocusListWalker(content)
    # Focus the path edit
    walker.set_focus(2)
    urwid.WidgetWrap.__init__(self, urwid.LineBox(urwid.ListBox(walker)))

  def _on_load(self, button):
    path = self.path_edit.get_edit_text().strip()
    if path:
      self._result = (path, self.remember_checkbox.get_state())
      raise urwid.ExitMainLoop()

  def _on_cancel(self, button):
    raise urwid.ExitMainLoop()

  def keypress(self, size, key):
    if key == 'esc':
      raise urwid.ExitMainLoop()
    result = super().keypress(size, key)
    if result == 'enter':
      self._on_load(None)
      return
    return result

  def showModal(self, parent=None):
    if parent is None:
      parent = urwid.SolidFill()
    overlay = urwid.Overlay(self, parent, 'center', self.WIDTH, 'middle', self._height)
    urwid.MainLoop(overlay).run()
    return self._result

class UnlockDialog(urwid.WidgetWrap):
  """
  Unified database unlock dialog.

  Shows one row per discovered KeySource (passphrase field or unavailable
  notice), plus Unlock / Load Keyfile... / Quit buttons at the bottom.
  The dialog validates credentials internally via KeySource.try_unlock() and
  only closes once at least one key is successfully unlocked, or the user
  chooses Quit (or presses Esc).

  showModal() returns:
    ([(KeySource, passphrase)], [(path, remember_bool)])
  or raises SystemExit if the user quits.

  Designed to be extensible: future key types (FIDO2, etc.) just need
  a new row widget type; the validation loop is unchanged.
  """

  WIDTH = 60

  def __init__(self, key_sources, scan_key_file, redir_key_name='redir.key'):
    self._scan_key_file  = scan_key_file
    self._redir_key_name = redir_key_name
    self._result      = None
    self._quit_requested = False
    self._add_files   = []   # [(path, remember)] accumulated via Load Keyfile

    self._walker = urwid.SimpleFocusListWalker([])
    listbox = urwid.ListBox(self._walker)
    urwid.WidgetWrap.__init__(self, urwid.LineBox(listbox))
    self._build(key_sources)

  # ------------------------------------------------------------------
  # Widget building
  # ------------------------------------------------------------------

  def _build(self, key_sources):
    from koshdb.koshdb import KeySource
    rows = []
    height = 2  # title + section divider

    rows.append(urwid.Text('Unlock database', align='center'))
    rows.append(urwid.Divider('-'))

    # Sort: available passphrase sources first, unavailable sources below.
    available   = [ks for ks in key_sources if ks.source_type == KeySource.TYPE_PASSPHRASE]
    unavailable = [ks for ks in key_sources if ks.source_type != KeySource.TYPE_PASSPHRASE]
    sorted_sources = available + unavailable

    if sorted_sources:
      for i, ks in enumerate(sorted_sources):
        if i > 0:
          rows.append(urwid.Divider())
          height += 1
        src_rows = self._source_rows(ks)
        rows.extend(src_rows)
        height += self._source_height(ks)
    else:
      rows.append(urwid.Text('No key sources found.', align='center'))
      height += 1

    height += 2  # section divider + button row
    rows.append(urwid.Divider('-'))

    # Unlock / Load Keyfile... / Quit buttons
    unlock_btn   = urwid.Button('Unlock',        self._on_unlock)
    keyfile_btn  = urwid.Button('Load Key...', self._on_load_keyfile)
    quit_btn     = urwid.Button('Quit',          self._on_quit)
    rows.append(urwid.Columns([
        urwid.Padding(unlock_btn,  'center', 10),
        urwid.Padding(keyfile_btn, 'center', 15),
        urwid.Padding(quit_btn,    'center', 8),
    ]))

    self._height = height + 2  # +2 for LineBox border

    self._walker[:] = rows
    # Focus first passphrase field, falling back to first interactive widget
    for i, w in enumerate(self._walker):
      if isinstance(w, widgets.passwordEdit):
        self._walker.set_focus(i)
        break
    else:
      for i, w in enumerate(self._walker):
        if isinstance(w, (widgets.koshEdit, urwid.CheckBox, urwid.Columns)):
          self._walker.set_focus(i)
          break

  def _source_rows(self, ks):
    """Return a list of urwid widgets for one KeySource."""
    from koshdb.koshdb import KeySource
    if ks.source_type == KeySource.TYPE_PASSPHRASE:
      return self._passphrase_rows(ks)
    if ks.source_type == KeySource.TYPE_UNAVAILABLE:
      return self._unavailable_rows(ks)
    return [urwid.Text('Unknown key type %r: %s' % (ks.source_type, ks.source_file))]

  def _source_height(self, ks):
    """Return the number of display rows consumed by one KeySource."""
    from koshdb.koshdb import KeySource
    if ks.source_type == KeySource.TYPE_PASSPHRASE:
      return 3  # label + edit + error_text
    if ks.source_type == KeySource.TYPE_UNAVAILABLE:
      return 1  # single Columns row (error hidden until after Retry)
    return 1    # unknown fallback

  def _compute_height(self):
    """Count display rows consumed by current walker contents."""
    h = 2   # LineBox top + bottom borders
    for w in self._walker:
      if isinstance(w, urwid.Columns):
        # Unavailable source rows embed multi-line Text in the first column.
        try:
          first_w = w.contents[0][0]
          if isinstance(first_w, urwid.Text):
            text, _ = first_w.get_text()
            h += text.count('\n') + 1
            continue
        except (IndexError, AttributeError):
          pass
      h += 1
    return h

  def _refresh_overlay(self):
    """Resize the overlay to fit current walker contents."""
    if not hasattr(self, '_loop'):
      return
    h = min(self._compute_height(), 40)
    self._loop.widget = urwid.Overlay(self, self._parent, 'center',
                                      self.WIDTH, 'middle', h)

  def _passphrase_rows(self, ks):
    edit = widgets.passwordEdit('')
    edit._key_source = ks
    error_text = urwid.Text('')
    ks._edit = edit
    ks._error_widget = error_text
    return [
      urwid.Text('Passphrase for %s:' % ks.source_file),
      edit,
      error_text,
    ]

  def _unavailable_rows(self, ks, show_error=False):
    retry_btn = urwid.Button('Retry')
    urwid.connect_signal(retry_btn, 'click', self._on_retry, ks)
    if show_error and ks.error:
      label = 'Unavailable: %s\n  %s' % (ks.source_file, ks.error)
    else:
      label = 'Unavailable: %s' % ks.source_file
    cols = urwid.Columns([
      urwid.Text(label),
      ('fixed', 9, retry_btn),
    ], dividechars=1)
    ks._retry_widget = cols
    return [cols]

  # ------------------------------------------------------------------
  # Event handlers
  # ------------------------------------------------------------------

  def _on_load_keyfile(self, button):
    """Open the Add Key File dialog; insert any resulting sources."""
    dialog = AddKeyFileDialog(self._redir_key_name)
    result = dialog.showModal()
    if not result:
      return
    path, remember = result
    self._add_files.append((path, remember))

    new_sources = self._scan_key_file(path)
    # Insert new source rows just above the section divider before the buttons
    # (last 2 walker entries are: divider, button row)
    insert_at = max(0, len(self._walker) - 2)
    insert_rows = []
    for i, ns in enumerate(new_sources):
      if i > 0 or insert_at > 2:
        insert_rows.append(urwid.Divider())
      insert_rows.extend(self._source_rows(ns))
    if insert_rows:
      self._walker[insert_at:insert_at] = insert_rows
    self._refresh_overlay()

  def _on_retry(self, button, ks):
    """Re-scan an unavailable source; replace its row on success or show error."""
    new_sources = self._scan_key_file(ks.source_file)
    # Use identity comparison — walker is a list but widget __eq__ is unreliable
    idx = next((i for i, w in enumerate(self._walker) if w is ks._retry_widget), None)
    if idx is None:
      return
    if new_sources:
      new_rows = []
      for ns in new_sources:
        new_rows.extend(self._source_rows(ns))
      self._walker[idx:idx+1] = new_rows
    else:
      # Still unavailable — now show the error detail
      self._walker[idx:idx+1] = self._unavailable_rows(ks, show_error=True)
    self._refresh_overlay()

  def _on_unlock(self, button):
    """Try to unlock with all filled-in passphrases."""
    unlocked = []
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
      try:
        ks.try_unlock(passphrase)
        unlocked.append((ks, passphrase))
        if hasattr(ks, '_error_widget'):
          ks._error_widget.set_text('')
      except Exception:
        if hasattr(ks, '_error_widget'):
          ks._error_widget.set_text(('error', 'Incorrect passphrase'))

    if unlocked:
      self._result = (unlocked, self._add_files)
      raise urwid.ExitMainLoop()

  def _on_quit(self, button):
    self._quit_requested = True
    raise urwid.ExitMainLoop()

  # ------------------------------------------------------------------
  # Input handling
  # ------------------------------------------------------------------

  def keypress(self, size, key):
    if key == 'esc':
      self._quit_requested = True
      raise urwid.ExitMainLoop()

    # Pass the key to the inner widgets first; handle what they don't consume.
    result = super().keypress(size, key)

    if result == 'enter':
      self._on_unlock(None)
      return   # consumed

    return result

  # ------------------------------------------------------------------
  # Modal loop
  # ------------------------------------------------------------------

  def showModal(self, parent=None):
    if parent is None:
      parent = urwid.SolidFill()
    self._parent = parent
    height = min(self._height, 40)
    overlay = urwid.Overlay(self, parent, 'center', self.WIDTH,
                            'middle', height)
    palette = [('error', 'dark red', '')]
    self._loop = urwid.MainLoop(overlay, palette=palette)
    self._loop.run()
    if self._quit_requested:
      raise SystemExit(0)
    return self._result


if __name__=='__main__':
  d = inputDialog(message='Enter master password:', width=30)
  print(d.showModal())
