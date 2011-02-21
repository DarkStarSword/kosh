#!/usr/bin/env python2.6
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

def get_next_action_ask():
  pass

def get_next_action_scripted(script):
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
  state = object()
  # If replaying a script, use get_next_action_scripted
  get_next_action = get_next_action_ask()
  while True:
    action = get_next_action(state)
    print action


if __name__ == '__main__':
  #test_expect_groups()
  main()
