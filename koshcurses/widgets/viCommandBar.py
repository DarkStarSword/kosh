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
      'esc': 'end_search',
      'enter': 'search',
    },
  }
  COMMANDS = {
    'q': 'quit',
    'help': 'help',
    'set': 'set_variable',
  }

  def __init__(self, body, search_function=None):
    self._search_function = search_function

    self.defaults()
    self._status = urwid.Text('')
    self._container = urwid.Frame(body, footer = self._status)
    self.normal_mode()
    urwid.WidgetWrap.__init__(self, self._container)

  def defaults(self):
    if not hasattr(self, 'variables'):
      self.variables = {}
    self.variables.update({
      'incsearch': True,
    })

  def update_status(self, status, append=False):
    if type(status) in (str, unicode):
      if append and self._status.text:
        self._status = urwid.Text(self._status.text + '\n' + status)
      else:
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
    original_mode = self._mode
    if original_mode == 'NORMAL':
      key = self._container.keypress(size, key)
      #self.update_status(repr(key))

    km = self.KEYMAP[self._mode]
    if key in km:
      f = getattr(self, km[key])
      if f.__code__.co_argcount == 3:
        return f(size, key)
      return f()

    if original_mode == 'NORMAL':
      # Already allowed child widgets to process this
      return key
    try:
      key = self._container.keypress(size, key)
      if self._mode == 'SEARCH' and self.variables['incsearch']:
        self.incsearch()
      return key
    except viStatusEdit.Cancel:
      self.normal_mode()
      return None

  def exec_command(self):
    args = self._status.get_edit_text().split(None, 1)
    self.normal_mode()
    if not args:
      return
    (command,args) = (args[0], args[1] if len(args) > 1 else None)
    if command in self.COMMANDS:
      getattr(self, self.COMMANDS[command])(args)
    else:
      self.update_status('Unknown command: '+command)

  def _search(self):
    search = self._status.get_edit_text()
    return self._search_function(search)
  
  def incsearch(self):
    self._search()

  def end_search(self, *args):
    self._search_function(None)
    self.normal_mode()

  def search(self, *args):
    ret = self._search()
    self.normal_mode()
    if ret is None:
      self.update_status('search cancelled')
    else:
      self.update_status('matched %i %s'%(ret, 'entry' if ret == 1 else 'entries'))
      if ret == 0:
        self._search_function(None)

  def quit(self, args):
    raise urwid.ExitMainLoop()

  def help(self, args):
    # STUB. TODO: Help message. FIXME: Align. Perhaps better command names
    # FIXME: Display by main contents and handling special mode
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

  def displayVariables(self, vars):
    # FIXME: Display by main contents and handling special mode
    def exit_on_input(input):
      if input.lower() in ['esc', 'q', 'enter']:
        raise urwid.ExitMainLoop()

    if vars is None:
      vars = self.variables.keys()
    contents = []
    for v in vars:
      if v not in self.variables:
        contents += ['Unknown variable: %s'%v]
      elif isinstance(self.variables[v],bool):
        if self.variables[v]:
          contents += [v]
        else:
          contents += ['no%s'%v]
      else:
        contents += ['%s=%s'%(v,self.variables[v] if v in self.variables else '')]
    container = urwid.ListBox(map(urwid.Text,contents))
    urwid.MainLoop(container, unhandled_input = exit_on_input).run()

  def set_variable(self, args):
    if not args:
      return self.displayVariables(None)
    updateVars={}
    showArgs=[]
    args = args.split()
    while len(args):
      var = args.pop(0)
      if '=' in var:
        (v,s) = var.split('=',1)
        s += ' '.join(args)
        args = []
      else:
        if var.startswith('no'):
          (v,s) = (var.lstrip('no'), False)
        else:
          (v,s) = (var, True)
      if v not in self.variables:
        return self.update_status('Unknown option: %s'%v)
      elif s==True and not isinstance(self.variables[v],bool):
        showArgs += [v]
      elif type(self.variables[v]) != type(s):
          return self.update_status('Invalid Argument: %s'%var)
      else:
        updateVars[v] = s
    if showArgs:
      return self.displayVariables(showArgs)
    self.variables.update(updateVars)

if __name__ == '__main__':
  b = urwid.SolidFill('x')
  v = viCommandBar(b)
  v.help()
