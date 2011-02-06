#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab

import urwid

class viStatusEdit(urwid.Edit):
  """
  Standard urwid exit that raises viStatusEditCancel if backspace is pressed
  with empty input.
  """
  class Cancel(Exception): pass
  def keypress(self, size, key):
    if key == 'backspace' and not self.get_edit_text():
      raise self.Cancel
    return urwid.Edit.keypress(self, size, key)

class viCommandBar(urwid.WidgetWrap):
  """
  WIP urwid widget to implement a vi style status, command & search bar.

  TODO: Search while you type
  """
  # FIXME: Add validation routine to ensure functions exist
  KEYMAP = {
    'NORMAL': {
      ':': 'command_mode',
      '/': 'search_mode',
    },
    'COMMAND': {
      'esc': 'normal_mode',
      'enter': 'exec_command',
    },
    'SEARCH': {
      'esc': 'normal_mode',
      'enter': 'search',
    },
  }
  COMMANDS = {
    'q': 'quit',
    'help': 'help',
  }

  def __init__(self, body, search_function=None):
    self._search_function = search_function

    self._status = urwid.Text('')
    self._container = urwid.Frame(body, footer = self._status)
    self.normal_mode()
    urwid.WidgetWrap.__init__(self, self._container)

  def update_status(self, status):
    if type(status) == str:
      self._status = urwid.Text(status)
    else:
      self._status = status
    self._container.footer = self._status

  def normal_mode(self):
    self._mode = 'NORMAL'
    self.update_status('For help on keys, enter :help')
    self._container.set_focus('body')

  def command_mode(self):
    self._mode = 'COMMAND'
    self.update_status(viStatusEdit(caption=':'))
    self._container.set_focus('footer')

  def search_mode(self):
    if self._search_function is None:
      self.normal_mode
      self.update_status('Search feature not implemented')
      return
    self._mode = 'SEARCH'
    self.update_status(viStatusEdit(caption='/'))
    self._container.set_focus('footer')

  def keypress(self, size, key):
    km = self.KEYMAP[self._mode]
    if key in km:
      f = getattr(self, km[key])
      if f.__code__.co_argcount == 3:
        return f(size, key)
      return f()
    try:
      return self._container.keypress(size, key)
    except viStatusEdit.Cancel:
      self.normal_mode()

  def exec_command(self):
    args = self._status.get_edit_text().split()
    self.normal_mode()
    if not args:
      return
    command = args.pop(0)
    if command in self.COMMANDS:
      getattr(self, self.COMMANDS[command])(args)
    else:
      self.update_status('Unknown command: '+command)

  def search(self, size, key):
    self._search_function(self._status.get_edit_text())
    normal_mode()
    self.update_status('search '+key)

  def quit(self, *args):
    raise urwid.ExitMainLoop()

  def help(self, *args):
    # STUB. TODO: Help message. FIXME: Align. Perhaps better command names
    def exit_on_input(input):
      if input.lower() in ['esc', 'q']:
        raise urwid.ExitMainLoop()

    contents = [urwid.Text('Commands:')]
    for command in self.COMMANDS:
      contents += [urwid.Text('  :%s - %s'%(command, self.COMMANDS[command]))]
    for mode in self.KEYMAP:
      contents += [urwid.Divider(),urwid.Text('%s mode:'%mode)]
      for key in self.KEYMAP[mode]:
        contents += [urwid.Text('  %s - %s'%(key, self.KEYMAP[mode][key]))]
    container = urwid.ListBox(contents)
    urwid.MainLoop(container, unhandled_input = exit_on_input).run()

if __name__ == '__main__':
  b = urwid.SolidFill('x')
  v = viCommandBar(b)
  v.help()
