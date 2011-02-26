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

# FIXME: Move into tty ui class
def get_next_char(prompt):
  import sys, tty
  stdin = sys.stdin.fileno()
  if prompt:
    print prompt,
  old = tty.tcgetattr(stdin)
  try:
    tty.setcbreak(stdin)
    ch = sys.stdin.read(1)
  finally:
    tty.tcsetattr(stdin, tty.TCSADRAIN, old)
  print "\x08%s"%ch
  return ch

class urlvcr_action(object):
  def valid(self, state):
    raise NotImplementedError()
  def help(self, state):
    return "Missing help text"
  def ask_params(self, state):
    return None

class action_goto(urlvcr_action):
  def valid(self, state):
    return True
  def help(self, state):
    return "Goto URL"
  def ask_params(self, state):
    url = raw_input('Enter URL')
    if not url.find('://'):
      if get_next_char("No protocol specified - assume http? (Y,n)"):
      url = 'http://'+url

class urlvcr_actions(object):
  def __init__(self, actions):
    self.actions = actions

  def display_valid_actions(self, state):
    for action in self.actions:
      if self.actions[action].valid(state):
        print "  %s: %s"%(action, self.actions[action].help(state))

  def ask_next_action(self, state):
    import sys
    action=''
    print "-------------"
    while True:
      print "Enter action:"
      actions.display_valid_actions(state)
      action = get_next_char("> ").lower()
      if action not in self.actions:
        print "%s: Invalid action\n"%repr(action)
        continue
      params = self.actions[action].ask_params(state)
      return (action, params)

actions = urlvcr_actions({
  'g': action_goto(),
})

def get_actions_ask(state):
  while True:
    yield actions.ask_next_action(state)

def get_actions_from_script(state, script):
  # Intended to be used as a generator to return the actions in the script
  pass

class urlvcr(object):
  """
  Linked list of states, including URL, cookies, etc. Used to produce a script
  for later replay.
  """
  class urlstate(object):
    def __init__(self, parent=None):
      self.parent = parent

  def __init__(self):
    self.state = urlvcr.urlstate()

def main():
  script = []
  state = urlvcr()
  # If replaying a script, use get_actions_from_script
  get_next_action = get_actions_ask(state)
  while True:
    action = get_next_action.next()
    script.append(action)
    print action


if __name__ == '__main__':
  #test_expect_groups()
  main()
