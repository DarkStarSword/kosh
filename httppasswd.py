#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab

# URLs will be a difficult case...
#  state -> logging in
#  goto URL
#  submit form | submit password
#  state -> logged in | failed
#  if logged in:
#   { goto URL || follow link }
#   state -> changing password
#   submit form
#   state -> password possibly changed | password changed | change failed
#   log out
# VERIFY:
#  state -> verifying change
#  goto URL
#  submit form | submit password
#  state -> change succeeded | verification stage failed
#
# Actions for:
#  GOTO URL
#  Follow link on page (regexp match?)
#  Fill in form
#  Submit form

import urllib2

TIMEOUT=10 # FIXME: Configurable
DEBUG=True

class urlvcr_action(object):
  def valid(self, state):
    raise NotImplementedError()
  def help(self, state):
    return "Missing help text"
  def ask_params(self, ui, state):
    return None
  def apply(self, ui, state, params):
    raise NotImplementedError()
  changes_state = True # Default unless action defines otherwise

class action_debug(urlvcr_action):
  counter = 0
  def valid(self,state): return DEBUG
  def apply(self, ui, state, params):
    fp = open('index.html')
    if params:
      state.url = params
    else:
      state.url = 'DEBUG %i'%self.counter
      self.counter += 1
    state.body = fp.read()
    fp.close()

class action_goto(urlvcr_action):
  def valid(self, state):
    return True
  def help(self, state):
    return "Goto URL"
  def ask_params(self, ui, state):
    while True:
      url = ''
      while url == '':
        url = raw_input('Enter URL: ')
      if url.find('://') != -1:
        break
      if ui.read_nonbuffered("No protocol specified - assume http? (Y,n) "):
        url = 'http://'+url
        break
    return url

  def apply(self, ui, state, url):
    state.request(ui, url)

class action_quit(urlvcr_action):
  changes_state = False
  def valid(self, state):
    return True
  def help(self, state):
    return "Quit, discarding script (for now)"
  def ask_params(self, ui, state):
    raise StopIteration('Quit')

class action_undo(urlvcr_action):
  changes_state = False # Technically we do, but this prevents a new state being pushed
  def valid(self, state):
    return state.state is not None
  def help(self, state):
    return "Undo last action (DANGEROUS: Server may have tracked state)"
  def apply(self, ui, state, params):
    state.pop()

class action_back(urlvcr_action):
  def valid(self, state):
    node = self._walk(state.state, 1)
    return node is not None
  def help(self, state):
    return "Go back in history (recording this as an action)"
  def apply(self, ui, state, params):
    # new state has already been pushed, so need parent of parent:
    node = self._walk(state.parent, 1)
    if node.url.startswith('DEBUG'):
      return actions['#'].apply(ui, state, node.url+'b')
    state.request(ui, node.url)
  def _walk(self, node, num):
    while node and (num or node.action[0] == 'b'):
      if node.action[0] == 'b':
        params = node.action[1]
        num += params if params else 1
      else:
        num -= 1
      node = node.parent
    return node


class urlvcr_actions(dict):
  def display_valid_actions(self, ui, state):
    for action in sorted(self):
      if self[action].valid(state):
        ui._print("  %s: %s"%(action, self[action].help(state)))

  def ask_next_action(self, ui, state):
    import sys
    action=''
    ui._print("-------------")
    while True:
      ui._print("Enter action:")
      actions.display_valid_actions(ui, state)
      action = ui.read_nonbuffered("> ").lower()
      if action not in self or not self[action].valid(state):
        ui._print("%s: Invalid action from current state\n"%repr(action))
        continue
      params = self[action].ask_params(ui, state)
      return (action, params)

# ABI WARNING: Do not reassign letters without bumping db version & implementing conversion - these are saved in the scripts
actions = urlvcr_actions({
  '#': action_debug(),
  'g': action_goto(),
  'q': action_quit(),
  'u': action_undo(),
  'b': action_back(),
})

def get_actions_ask(ui, state):
  while True:
    yield actions.ask_next_action(ui, state)

def get_actions_from_script(state, script):
  # STUB: Intended to be used as a generator to return the actions in the script
  pass

def apply_action(ui, state, action):
  a = actions[action[0]]
  if a.changes_state:
    state.push(action)
  try:
    a.apply(ui, state, action[1])
  except urllib2.URLError, e:
    assert(a.changes_state)
    ui._cprint('dark red', 'Unhandled URLError, undoing last action')
    state.pop()

class urlvcr(object):
  """
  Linked list of states, including URL, cookies, etc. Used to produce a script
  for later replay.
  """
  state = None

  class urlstate(object):
    def __init__(self, parent, action):
      self.parent = parent
      self.action = action
      if self.parent:
        self.opener = self.parent.opener
        self.url = self.parent.url
        self.info = self.parent.info
        self.body = self.parent.body
      else:
        self.opener = urllib2.build_opener()
        self.url = None
        self.info = None
        self.body = None

    def list(self):
      ret = []
      if self.parent is not None:
        ret = self.parent.list()
      return ret + [{'action': self.action, 'url': self.url}] #, 'info': self.info, 'body': self.body}]

  def push(self, action):
    self.state = urlvcr.urlstate(self.state, action)

  def pop(self):
    assert(self.state is not None)
    self.state = self.state.parent

  def request(self, ui, url):
    # FIXME: show progress:
    request = urllib2.Request(url)
    try:
      response = self.state.opener.open(request, timeout=TIMEOUT)
    except urllib2.URLError, e:
      if hasattr(e, 'reason'):
        ui._cprint('red', 'Failed to reach server: %s'%e.reason)
      elif hasattr(e, 'code'):
        ui._cprint('ref', 'HTTP status code: %s'%e.code)
      raise
    self.state.url = response.geturl()
    self.state.info = response.info()
    self.state.body = response.read()

  def __str__(self):
    if self.state is None:
      return ''
    return '\n'.join([ "%i: %s"%(i,repr(a)) for (i,a) in enumerate(self.state.list())])

  def __getattribute__(self, name):
    try:
      return object.__getattribute__(self, name)
    except AttributeError:
      return object.__getattribute__(self.state, name)

  def __setattr__(self, name, val):
    if hasattr(self.state, name):
      return self.state.__setattr__(name, val)
    else:
      return object.__setattr__(self, name, val)

def main(ui):
  #script = []
  state = urlvcr()
  # If replaying a script, use get_actions_from_script
  action_seq = get_actions_ask(ui, state)
  for action in action_seq:
    apply_action(ui, state, action)
    #script.append(action)
    #print action
    print state


if __name__ == '__main__':
  #test_expect_groups()
  import ui.ui_tty
  main(ui.ui_tty())
