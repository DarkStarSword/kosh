#!/usr/bin/env python2.6
# vi:sw=2:ts=2:expandtab

from __future__ import print_function

import pexpect

ttycolours = {
    'dark red'    : '[0;31;40m',
    'red'         : '[1;31;40m',
    'dark green'  : '[0;32;40m',
    'green'       : '[1;32;40m',
    'dark yellow' : '[0;33;40m',
    'yellow'      : '[1;33;40m',
    'dark blue'   : '[0;34;40m',
    'blue'        : '[1;34;40m',
    'reset'       : '[0;37;40m',
}

def cprint(colour, msg, sep=' ', end='\n', file=None):
  try:
    print(ttycolours[colour] + msg + ttycolours['reset'], sep=sep, end=end, file=file)
  except KeyError:
    raise

def confirm(prompt, default=None):
  ret = ''
  prompt = prompt + ' ' + {
      True:  '(Y,n)',
      False: '(y,N)',
      None:  '(y,n)',
      }[default] + ': '
  while ret not in ['y', 'n']:
    ret = raw_input(prompt).lower()
    if default is not None and ret == '':
      return default
  return ret == 'y'

def cconfirm(colour, prompt, default=None):
  try:
    return confirm(ttycolours[colour] + prompt + ttycolours['reset'], default=default)
  except KeyError:
    raise

old_pass_prompts = [
    'current.*password: ',
    'Old Password: ',
    'Enter login\(LDAP\) password: ',
    '\(current\) UNIX password: ',
    ]

new_pass_prompts = [
    'Enter new password: ',
    'New Password: ',
    'Enter new UNIX password: ',
    ]

confirm_pass_prompts = [
    'Re-type new password: ',
    'Retype new UNIX password: ',
    'Re-enter new password: ',
    'Reenter New Password: ',
    ]

# TODO: Find more failure prompts
failure_prompts = [
    'password unchanged',
    ]

success_prompts = [
    'Password changed.',
    'passwd: password updated successfully',
    ]

def flatten1(l):
  """
  Flattens a list of lists by one level
     [[a,b,c],[d,e,f],[g,h,[i,j,k]]]
  => [ a,b,c,  d,e,f,  g,h,[i,j,k]]
  """
  return reduce(lambda a,b:a+b, l)

def expect_groups(self, groups):
  flatten = flatten1(groups)
  ret = self.expect(flatten)
  newgroups = flatten1([[g]*len(g) for g in groups])
  return newgroups[ret]

def test_expect_groups():
  groups = [old_pass_prompts, new_pass_prompts, confirm_pass_prompts, failure_prompts, success_prompts]
  for g in groups:
    for prompt in g:
      # Replace regular expressions with literals:
      prompt = reduce(lambda x,(a,b): x.replace(a,b), [('\(','('),('\)',')')], prompt)
      print("testing response to '%s': "%prompt,end='')
      self = pexpect.spawn("echo '%s'"%prompt)
      ret = expect_groups(self, groups)
      self.close()
      if ret != g:
        print("\nfail:'\nMatched %s\nnot     %s\n"%(e,str(ret),str(g)))
      else:
        print('ok')

def change_tty_passwd(oldpass, newpass, tty=None):
  if tty is None:
    cprint('yellow', "Changing local password")
    tty = pexpect.spawn('passwd')
  else:
    tty.prompt()
    tty.sendline('passwd')

  cprint('yellow','waiting for current password prompt...')
  # FIXME: Alternate prompts?
  result = tty.expect(['current.*password: ', 'Old Password: ', pexpect.TIMEOUT, pexpect.EOF])
  if result >= 2:
    cprint('red', 'timeout or EOF while waiting for current password prompt')
    print(tty.before)
    raise PasswordChangeFailure()

  cprint('yellow','sending old password...')
  tty.sendline(oldpass)

  result = tty.expect(['Enter new password: ', 'New Password: ', 'password unchanged', pexpect.TIMEOUT, pexpect.EOF])
  if result >= 2:
    cprint('red', 'Wrong old password')
    print(tty.before)
    raise PasswordChangeFailure()

  # cprint('yellow','sending new password...')
  # tty.sendline(newpass)

  # result = tty.expect(['Re-type new password: ', 'Reenter New Password: ', 'password unchanged', pexpect.TIMEOUT, pexpect.EOF])
  # if result >= 2:
  #   cprint('red', 'Problem with new password')
  #   print(tty.before)
  #   raise PasswordChangeFailure() # FIXME - could have changed

  # cprint('yellow','Re-sending new password...')
  # tty.sendline(newpass)

  # result = tty.expect(['Password changed.', pexpect.TIMEOUT, pexpect.EOF])
  # if result >= 1:
  #   cprint('red', 'Confirming new password appears to have failed?')
  #   print(tty.before)
  #   raise PasswordChangeFailure() # FIXME - could have changed

  tty.close(True)
  # FIXME: Look at passwd code for other possible results

class LoginFailure(Exception): pass

def ssh_open(host, username, password = '', force_password = True):
  import pxssh
  s = pxssh.pxssh()
  s.force_password = force_password
  try:
    s.login(host, username, password)
    print(s.before)
  except pxssh.ExceptionPxssh, e:
    raise LoginFailure(str(e))
  except pexpect.EOF, e:
    raise LoginFailure('EOF: Check the hostname')
  except pexpect.TIMEOUT, e: raise
  return s

class PasswordChangeFailure(Exception): pass         # Password was NOT changed
class PasswordChangeVerifyFailure(Exception): pass   # Password changed, but verification failed

def verify_ssh_passwd(host, username, password):
  try:
    s = ssh_open(host, username, password)
    s.logout()
    s.close(True)
    return True
  except LoginFailure, e:
    return False
  except pexpect.TIMEOUT, e: raise

def change_ssh_passwd(host, username, oldpass, newpass):
  # Login:
  print('Logging in to %s...'%host, end='')
  try:
    s = ssh_open(host, username, oldpass)
    cprint('green', 'Ok')
  except LoginFailure, e:
    cprint('red', 'failure: %s'%str(e))
    raise PasswordChangeFailure(str(e))

  print('Changing password...', end='')
  # Change:
  try:
    change_tty_passwd(oldpass, newpass, s)
  except:
    cprint('red', 'Exception while attempting to change password')

  # Logout:
  s.logout()
  s.close(True)

  # Verify:
  print('Verifying change on %s...'%host, end='')
  if verify_ssh_passwd(host, username, newpass):
    cprint('green', ' Success')
  else:
    cprint('red', ' Failure')
    print('Testing old password...', end='')
    if verify_ssh_passwd(host, username, oldpass):
      cprint('yellow', ' Password unchanged!')
      raise PasswordChangeFailure()
    else:
      cprint('red', ' Verification Failed!')
      raise PasswordChangeVerifyFailure()

# Proposed API:
# change takes: 
#  machine entry
#  old password entry
#  new password entry (or just new password?)
#  User Interface callbacks
# change needs to return state:
#  Definitely not changed
#  Possibly changed
#  Definitely changed
#
# If verify method is available it will always be called so long as password could have/was changed (maybe always?)
# verify takes:
#  machine entry
#  password entry
#
# Probably need to pass some extra state between these as well
#
#
#  User Interface callbacks
#ChangeMethods = {
#    'ssh': {'change': change_ssh_passwd,
#            'verify': test_ssh_passwd}
#    'config': {'change': change_config}
#    }
#
# Possibly I should also add a login/logout pair...
#
#
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
#
#

def update_config(filename, oldpass, newpass):
  import tempfile, os, re, difflib

  # Fixme: handle errors
  fp = open(filename, 'rb')
  original = fp.readlines()
  fp.close()

  oldcompiled = re.compile(r'\b%s\b'%oldpass)
  newcompiled = re.compile(r'\b%s\b'%newpass)
  modified = [ oldcompiled.sub(newpass, x) for x in original ]

  diff = list(difflib.unified_diff(original, modified, filename, filename))

  if diff == []:
    cprint('red', 'WARNING: Password not matched in %s, not updating'%filename)
    return False

  for line in diff:
    {
        '-' : lambda x : cprint('dark red', x, end=''),
        '+' : lambda x : cprint('dark green', x, end=''),
        '@' : lambda x : cprint('blue', x, end=''),
        }.get(line[0], lambda x : print(x, end='')) \
            (reduce(lambda x,(re,rep): re.sub(rep,x),
              [
                (oldcompiled, '<OLD PASS>'),
                (newcompiled, '<NEW PASS>')
              ], line))

  if cconfirm('blue', '\nApply change?', True):
    # FIXME: Handle errors
    # FIXME: Permissions?
    # FIXME: Symbolic links?
    with tempfile.NamedTemporaryFile(mode='wb', delete=False,
        prefix=os.path.basename(filename),
        dir=os.path.dirname(filename)) as fp:
      fp.writelines(modified)
      fp.close()
      if os.path.exists(filename):
        os.rename(filename, filename+'~')
      os.rename(fp.name, filename)

def main():
  import getpass, sys
  username = oldpass = newpass = newpass1 = ''
  #while username == '':
  #  username = raw_input('username: ')
  while oldpass == '':
    oldpass = getpass.getpass('old password: ')
  while newpass == '' or newpass != newpass1:
    newpass = getpass.getpass('new password: ')
    newpass1 = getpass.getpass('Confirm new password: ')


  # for host in sys.argv[1:]:
  #   try:
  #     cprint('yellow', 'Verifying password on %s...'%host)
  #     if host == 'localhost':
  #       change_tty_passwd(oldpass, newpass)
  #     else:
  #       try:
  #         if verify_ssh_passwd(host, username, oldpass):
  #           cprint('green', 'Ok')
  #         else:
  #           cprint('red', 'not ok')
  #       except pexpect.TIMEOUT, e:
  #         cprint('red', 'timeout')
  #   except:
  #     cprint('red', 'Exception verifying password on %s'%host)

  # for host in sys.argv[1:]:
  #   try:
  #     cprint('yellow', 'Changing password on %s...'%host)
  #     if host == 'localhost':
  #       change_tty_passwd(oldpass, newpass)
  #     else:
  #       change_ssh_passwd(host, username, oldpass, newpass)
  #   except:
  #     cprint('red', 'Password change failed on %s'%host)

  for config in sys.argv[1:]:
    cprint('yellow', 'Updating %s...'%config)
    update_config(config, oldpass, newpass)

if __name__ == '__main__':
  #test_expect_groups()
  main()
