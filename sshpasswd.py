#!/usr/bin/env python2.6
# vi:sw=2:ts=2:expandtab

import pexpect

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

def expect_groups_exception(self, groups, exceptiongroups):
  """
  Like expect_groups, but if an entry in exceptiongroups is matched, this will
  raise the corresponding exception instead.
  exceptiongroups is a dict mapping expressions to exceptions
  """
  ret = expect_groups(self, groups + exceptiongroups.keys())
  if ret in groups:
    return ret
  raise exceptiongroups[ret]


def test_expect_groups(ui):
  groups = [old_pass_prompts, new_pass_prompts, confirm_pass_prompts, failure_prompts, success_prompts]
  for g in groups:
    for prompt in g:
      # Replace regular expressions with literals:
      prompt = reduce(lambda x,(a,b): x.replace(a,b), [('\(','('),('\)',')')], prompt)
      ui._print("testing response to '%s': "%prompt,end='')
      self = pexpect.spawn("echo '%s'"%prompt)
      ret = expect_groups(self, groups)
      self.close()
      if ret != g:
        ui._print("\nfail:'\nMatched %s\nnot     %s\n"%(e,str(ret),str(g)))
      else:
        ui._print('ok')

def change_tty_passwd(ui, oldpass, newpass, tty=None):
  if tty is None:
    ui._cprint('yellow', "Changing local password")
    tty = pexpect.spawn('passwd')
  else:
    tty.prompt()
    tty.sendline('passwd')

  state = PasswordChangeFailure

  try:
    # FIXME: root user will not be prompted for current password
    ui._print('waiting for current password prompt...')
    result = expect_groups(tty, [old_pass_groups])

    ui._cprint('yellow','sending old password...')
    tty.sendline(oldpass)

    result = expect_groups_exception(tty, [new_pass_prompts],
        {failure_prompts: state('Bad old password!')})

    state = PasswordChangeFailure # FIXME: From here on it is possible that the change succeeds

    ui._cprint('yellow','sending new password...')
    tty.sendline(newpass)

    result = expect_groups_exception(tty, [confirm_pass_prompts],
        {failure_prompts: state('Problem with new password')})

    ui._cprint('yellow','Re-sending new password...')
    tty.sendline(newpass)

    result = expect_groups_exception(tty, [success_prompts],
        {failure_prompts: state('Confirming new password appears to have failed?')})

  except PasswordChangeFailure, e:
    ui._cprint('red', str(e))
    #print log
    raise
  except pexpect.TIMEOUT:
    ui._cprint('red', 'timeout')
    #print log
    raise state()
  except pexpect.EOF:
    ui._cprint('red', 'Unexpected end of output')
    #print log
    raise state()
  finally:
    tty.close(True)

class LoginFailure(Exception): pass

def replace_synch_original_prompt (self):
  import time
  """
  Overriding the pxssh method to allow the inital read to timeout if there is
  nothing to read.
  """
  try:
    self.read_nonblocking(size=10000,timeout=1) # GAS: Clear out the cache before getting
  except pexpect.TIMEOUT: pass
  time.sleep(0.1)
  self.sendline()
  time.sleep(0.5)
  x = self.read_nonblocking(size=1000,timeout=1)
  time.sleep(0.1)
  self.sendline()
  time.sleep(0.5)
  a = self.read_nonblocking(size=1000,timeout=1)
  time.sleep(0.1)
  self.sendline()
  time.sleep(0.5)
  b = self.read_nonblocking(size=1000,timeout=1)
  ld = self.levenshtein_distance(a,b)
  len_a = len(a)
  if len_a == 0:
      return False
  if float(ld)/len_a < 0.4:
      return True
  return False

def ssh_open(ui, host, username, password = '', force_password = True):
  import pxssh
  import StringIO
  log = StringIO.StringIO() # or just sys.stdout?
  pxssh.pxssh.synch_original_prompt = replace_synch_original_prompt
  s = pxssh.pxssh(logfile=log)
  s.force_password = force_password
  try:
    s.login(host, username, password)
  except pxssh.ExceptionPxssh, e:
    raise LoginFailure(str(e))
  except pexpect.EOF, e:
    raise LoginFailure('EOF: Check the hostname')
  except pexpect.TIMEOUT, e:
    raise
  finally:
    ui._print(log.getvalue().replace(password, '<OLD PASS>'))
  return s

class PasswordChangeFailure(Exception): pass         # Password was NOT changed
class PasswordChangeVerifyFailure(Exception): pass   # Password changed, but verification failed

def verify_ssh_passwd(ui, host, username, password):
  try:
    s = ssh_open(ui, host, username, password)
    s.logout()
    s.close(True)
    return True
  except LoginFailure, e:
    return False
  except pexpect.TIMEOUT, e: raise

def change_ssh_passwd(ui, host, username, oldpass, newpass):
  # Login:
  ui._print('Logging in to %s...'%host, end='')
  try:
    s = ssh_open(ui, host, username, oldpass)
    ui._cprint('green', 'Ok')
  except LoginFailure, e:
    ui._cprint('red', 'failure: %s'%str(e))
    raise PasswordChangeFailure(str(e))

  ui._print('Changing password...', end='')
  # Change:
  try:
    change_tty_passwd(ui, oldpass, newpass, s)
  except:
    ui._cprint('red', 'Exception while attempting to change password')

  # Logout:
  s.logout()
  s.close(True)

  # Verify:
  ui._print('Verifying change on %s...'%host, end='')
  if verify_ssh_passwd(ui, host, username, newpass):
    ui._cprint('green', ' Success')
  else:
    ui._cprint('red', ' Failure')
    ui._print('Testing old password...', end='')
    if verify_ssh_passwd(ui, host, username, oldpass):
      ui._cprint('yellow', ' Password unchanged!')
      raise PasswordChangeFailure()
    else:
      ui._cprint('red', ' Verification Failed!')
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

def update_config(ui, filename, oldpass, newpass):
  import tempfile, os, re, difflib

  # Fixme: handle errors
  try:
    fp = open(filename, 'rb')
    original = fp.readlines()
    fp.close()
  except IOError, e:
    ui._cprint('red', 'IOError processing %s: %s'%(filename, str(e)))
    raise PasswordChangeFailure()

  oldcompiled = re.compile(r'\b%s\b'%oldpass)
  newcompiled = re.compile(r'\b%s\b'%newpass)
  modified = [ oldcompiled.sub(newpass, x) for x in original ]

  diff = list(difflib.unified_diff(original, modified, filename, filename))

  if diff == []:
    ui._cprint('red', 'WARNING: Password not matched in %s, not updating'%filename)
    return False

  for line in diff:
    {
        '-' : lambda x : ui._cprint('dark red', x, end=''),
        '+' : lambda x : ui._cprint('dark green', x, end=''),
        '@' : lambda x : ui._cprint('blue', x, end=''),
        }.get(line[0], lambda x : ui._print(x, end='')) \
            (reduce(lambda x,(re,rep): re.sub(rep,x),
              [
                (oldcompiled, '<OLD PASS>'),
                (newcompiled, '<NEW PASS>')
              ], line))

  if ui._cconfirm('blue', '\nApply change?', True):
    try:
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
    except IOError, e:
      raise PasswordChangeFailure(e)


class UnknownProtocol(Exception): pass
class ProtocolParseException(Exception): pass

def parse_proto(url):
  def parse_ssh(url):
    try:
      (user, host) = url.split('@', 1)
    except ValueError:
      raise ProtocolParseException('No username found in %s'%url)
    return (user, host)
  def unknown_proto(url):
    raise UnknownProtocol(proto)

  try:
    (proto, url) = url.split('://', 1)
  except ValueError:
    raise ProtocolParseException('No protocol found in %s'%url)
  return (proto, {
    'verifyssh' : parse_ssh,
    'ssh'       : parse_ssh,
    'localhost' : lambda x : None,
    'conf'      : lambda x : x,
    }.get(proto, unknown_proto)(url))


def main(ui):
  import getpass, sys

  urls = [parse_proto(x) for x in sys.argv[1:]]
  protos = set(zip(*urls)[0])

  if (len(urls) == 0):
    ui._print('No URLs specified')
    return

  oldpass = newpass = newpass1 = ''
  while oldpass == '':
    oldpass = getpass.getpass('old password: ')
  if protos.intersection(['ssh','conf']):
    while newpass == '' or newpass != newpass1:
      newpass = getpass.getpass('new password: ')
      newpass1 = getpass.getpass('Confirm new password: ')

  for (proto, data) in urls:
    if proto in ('verifyssh', 'ssh'):
      (username, host) = data

    if proto == 'verifyssh':
      try:
        ui._cprint('yellow', 'Verifying password on %s...'%host)
        if verify_ssh_passwd(ui, host, username, oldpass):
          ui._cprint('green', 'Ok')
        else:
          ui._cprint('red', 'not Ok')
      except pexpect.TIMEOUT, e:
        ui._cprint('red', 'timeout')
      except:
        import traceback
        ui._print(traceback.format_exc())
        ui._cprint('red', 'Exception verifying password on %s'%host)

    if proto == 'ssh': pass
      # try:
      #   ui._cprint('yellow', 'Changing password on %s...'%host)
      #   change_ssh_passwd(ui, host, username, oldpass, newpass)
      # except:
      #   ui._cprint('red', 'Password change failed on %s'%host)

    if proto == 'localhost':
      try:
        change_tty_passwd(ui, oldpass, newpass)
      except:
        ui._cprint('red', 'Local password change failed!')

    if proto == 'conf':
      try:
        ui._cprint('yellow', 'Updating %s...'%data)
        update_config(ui, data, oldpass, newpass)
      except:
        ui._cprint('red', 'Updating configuration file failed!')

if __name__ == '__main__':
  import ui.ui_tty
  ui = ui.ui_tty()
  #test_expect_groups(ui)
  main(ui)
