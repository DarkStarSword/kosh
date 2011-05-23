#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab

import pexpect

class _PasswordChangeException(Exception): pass                     # Base class for exceptions
class PasswordChangeFailure(_PasswordChangeException): pass         # Password was NOT changed
class PasswordChangePossibleFailure(_PasswordChangeException): pass # Cannot determine if the password change was successful
class PasswordChangeVerifyFailure(_PasswordChangeException): pass   # Password changed, but verification failed
class _PasswordChangeReprompted(_PasswordChangeException): pass     # Used for internal state tracking only

class hashable_list(list):
  def __hash__(self):
    h=''
    for (i,x) in enumerate(self):
      h += '%i: %s,'%(i,repr(x))
    return hash(h)

old_pass_prompts = hashable_list([
    'current.*password: ',
    'Old Password: ',
    'Enter login\(LDAP\) password: ',
    '\(current\) UNIX password: ',
    ])

new_pass_prompts = hashable_list([
    'Enter new password: ',
    'New password: ',
    'New Password: ',
    'Enter new UNIX password: ',
    'New UNIX password: '
    ])

confirm_pass_prompts = hashable_list([
    'Re-type new password: ',
    'Retype new UNIX password: ',
    'Re-enter new password: ',
    'Reenter New Password: ',
    ])

# TODO: Find more failure prompts
failure_prompts = hashable_list([
    'password unchanged',
    # 'You must choose a longer password', - prefer to detect re-prompting
    ])

success_prompts = hashable_list([
    'Password changed.',
    'passwd: password updated successfully',
    'passwd: all authentication tokens updated successfully.'
    ])

def flatten1(l):
  """
  Flattens a list of lists by one level
     [[a,b,c],[d,e,f],[g,h,[i,j,k]]]
  => [ a,b,c,  d,e,f,  g,h,[i,j,k]]
  """
  return reduce(lambda a,b:a+b, l)

def expect_groups(ui, self, groups):
  flatten = list(flatten1(groups))
  #ui._cprint("blue", "%s.expect(%s)"%(repr(self),repr(flatten)))
  ret = self.expect(flatten)
  newgroups = flatten1([[g]*len(g) for g in groups])
  return newgroups[ret]

def expect_groups_exception(ui, self, groups, exceptiongroups):
  """
  Like expect_groups, but if an entry in exceptiongroups is matched, this will
  raise the corresponding exception instead.
  exceptiongroups is a dict mapping expressions to exceptions
  """
  ret = expect_groups(ui, self, groups + exceptiongroups.keys())
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
      ret = expect_groups(ui, self, groups)
      self.close()
      if ret != g:
        ui._print("\nfail:'\nMatched %s\nnot     %s\n"%(e,str(ret),str(g)))
      else:
        ui._print('ok')

def change_tty_passwd(ui, oldpass, newpass, tty=None):
  mustclose = False
  if tty is None:
    ui._cprint('bright yellow', "Changing local password")
    tty = pexpect.spawn('passwd')
    mustclose = True
    import sys
    log = filteringIOProxy(sys.stdout, [(oldpass, ui._ctext('blue', '<OLD_PASS>')),(newpass, ui._ctext('blue', '<NEW_PASS>'))])
    # TODO: Want both logging to the same StringIO, but _send passing through the filtering proxy
    tty.logfile_read = sys.stdout
    tty.logfile_send = log
  else:
    tty.sendline('')
    tty.prompt()
    tty.sendline('passwd')

  state = PasswordChangeFailure

  try:
    ui._cprint('yellow', 'waiting for current password prompt...')
    result = expect_groups(ui, tty, [old_pass_prompts, new_pass_prompts])

    if result == old_pass_prompts: # root is not prompted for an old password
      #ui._cprint('bright yellow','sending old password...')
      tty.sendline(oldpass)

      result = expect_groups_exception(ui, tty, [new_pass_prompts],
          {failure_prompts: state('Bad old password!')})

    state = PasswordChangePossibleFailure

    #ui._cprint('bright yellow','sending new password...')
    tty.sendline(newpass)

    result = expect_groups_exception(ui, tty, [confirm_pass_prompts],
        {
          failure_prompts: state('Problem with new password'),
          new_pass_prompts: _PasswordChangeReprompted('Asked for new password again instead of expected request for confirmation. Log may contain additional detail.'),
        })

    #ui._cprint('bright yellow','Re-sending new password...')
    tty.sendline(newpass)

    reprompted = hashable_list(new_pass_prompts + confirm_pass_prompts)
    result = expect_groups_exception(ui, tty, [success_prompts],
        {
          failure_prompts: state('Confirming new password appears to have failed?'),
          reprompted: _PasswordChangeReprompted('Asked for new password again after confirming password - perhaps new password does not conform to system password policy? Log may contain additional detail.'),
        })

    return True

  except _PasswordChangeReprompted, e:
    mustclose = True
    ui._cprint('bright red','Got prompt for new password again')
    raise state(str(e))
  except PasswordChangeFailure, e:
    ui._cprint('bright red', str(e))
    #print log
    raise
  except pexpect.TIMEOUT:
    mustclose = True # Otherwise we might try entering 'exit' at a prompt
    ui._cprint('bright red', 'timeout')
    #print log
    raise state('TIMEOUT')
  except pexpect.EOF:
    ui._cprint('bright red', 'Unexpected end of output')
    #print log
    raise state('Unexpected EOF')
  finally:
    if mustclose:
      tty.close(True)

class LoginFailure(Exception): pass

def replace_synch_original_prompt (self):
  import time
  """
  Overriding the pxssh method to allow the inital read to timeout if there is
  nothing to read.

  Also, if the first attempt fails, try again with a larger round trip time for
  the prompt to appear after sending an enter press.
  """
  for rtt in [0.5, 1.5]:
      try:
        self.read_nonblocking(size=10000,timeout=1) # GAS: Clear out the cache before getting
      except pexpect.TIMEOUT: pass
      time.sleep(0.1)
      self.sendline()
      time.sleep(rtt)
      x = self.read_nonblocking(size=1000,timeout=1)
      time.sleep(0.1)
      self.sendline()
      time.sleep(rtt)
      a = self.read_nonblocking(size=1000,timeout=1)
      time.sleep(0.1)
      self.sendline()
      time.sleep(rtt)
      b = self.read_nonblocking(size=1000,timeout=1)
      ld = self.levenshtein_distance(a,b)
      len_a = len(a)
      if len_a == 0:
          continue
      if float(ld)/len_a < 0.4:
          return True
  return False

class filteringIOProxy(object):
  def __init__(self, fp, filters):
    self.fp = fp
    self._buf = ''
    self.filters = filters

  def write(self, str):
    self._buf += str
    lines = self._buf.split('\n')
    self._buf = lines[-1:][0]
    for line in lines[:-1]:
      self.fp.write(self.filter(line) + '\n')

  def flush(self):
    self.fp.write(self.filter(self._buf))
    self._buf = ''
    self.fp.flush()

  def filter(self, str):
    return reduce(lambda s,(rep,wit): s.replace(rep, wit), self.filters, str)

  def __getattribute__(self,name):
    try:
      return object.__getattribute__(self, name)
    except AttributeError:
      return object.__getattribute__(self, 'fp').__getattribute__(name)

def ssh_open(ui, host, username, password = '', force_password = True, filter=None):
  import pxssh
  #import StringIO
  #log = StringIO.StringIO()
  import sys
  if filter is None:
    filter = [(password, ui._ctext('blue', '<PASSWORD>'))]
  log = filteringIOProxy(sys.stdout, filter)
  pxssh.pxssh.synch_original_prompt = replace_synch_original_prompt
  s = pxssh.pxssh()
  # pxssh obviousely has never dealt with zsh and it's attempt to make the
  # prompt more unique will put a \ in the prompt that it doesn't expect, this
  # regexp optionally matches that \:
  s.PROMPT = "\[PEXPECT\]\\\\?[\$\#] "
  # TODO: Want both logging to the same StringIO, but _send passing through the filtering proxy
  s.logfile_read = sys.stdout
  s.logfile_send = log
  s.force_password = force_password
  try:
    s.login(host, username, password, original_prompt=r"[#$>] ")
  except pxssh.ExceptionPxssh, e:
    raise LoginFailure(str(e))
  except pexpect.EOF, e:
    raise LoginFailure('EOF: Check the hostname')
  except pexpect.TIMEOUT, e:
    raise
  #finally:
    # print log
  return s

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
  ui._cprint('yellow', 'Logging in to %s...'%host)
  try:
    s = ssh_open(ui, host, username, oldpass, filter=[(oldpass, ui._ctext('blue', '<OLD_PASS>')),(newpass, ui._ctext('blue', '<NEW_PASS>'))])
    ui._cprint('bright green', 'Ok')
  except LoginFailure, e:
    ui._cprint('bright red', 'failure: %s'%str(e))
    raise PasswordChangeFailure(str(e))

  ui._cprint('bright yellow', 'Changing password...')
  # Change:
  verifyException = None
  try:
    change_tty_passwd(ui, oldpass, newpass, s)
  except PasswordChangeFailure:
    # No need to verity, at this phase of the process it should not be possible to have inadvertently changed the password
    raise
  except PasswordChangePossibleFailure, e:
    # If we got this far it is possible we may have changed the password, so we
    # need to verify. If verification fails we want to re-raise this exception,
    # not VerifyFailure:
    verifyException = e
  finally:
    # Logout, ignore exceptions:
    try:
      if not s.closed:
        s.logout()
    except: pass
    try:
      s.close(True)
    except: pass

  # Verify:
  ui._cprint('bright yellow', 'Verifying password change on %s...'%host)
  ui._cprint('yellow', 'trying new password...')
  if verify_ssh_passwd(ui, host, username, newpass):
    return True
  else:
    ui._cprint('bright red', ' Failure')
    ui._cprint('yellow', 'Trying old password...')
    if verify_ssh_passwd(ui, host, username, oldpass):
      ui._cprint('bright yellow', ' Password unchanged!')
      if verifyException is not None:
        # If we possibly failed earlier, that exception will have more detail than we know now, so raise it:
        raise verifyException
      raise PasswordChangeFailure('Failed to verify password change, but old password still works')
    else:
      ui._cprint('bright red', ' Verification Failed!')
      if verifyException is not None:
        raise verifyException
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
    ui._cprint('bright red', 'IOError processing %s: %s'%(filename, str(e)))
    raise PasswordChangeFailure()

  oldcompiled = re.compile(r'\b%s\b'%oldpass)
  newcompiled = re.compile(r'\b%s\b'%newpass)
  modified = [ oldcompiled.sub(newpass, x) for x in original ]

  diff = list(difflib.unified_diff(original, modified, filename, filename))

  if diff == []:
    ui._cprint('bright red', 'WARNING: Password not matched in %s, not updating'%filename)
    return False

  for line in diff:
    {
        '-' : lambda x : ui._cprint('red', x, end=''),
        '+' : lambda x : ui._cprint('green', x, end=''),
        '@' : lambda x : ui._cprint('bright blue', x, end=''),
        }.get(line[0], lambda x : ui._print(x, end='')) \
            (reduce(lambda x,(re,rep): re.sub(rep,x),
              [
                (oldcompiled, '<OLD PASS>'),
                (newcompiled, '<NEW PASS>')
              ], line))

  if ui._cconfirm('bright blue', '\nApply change?', True):
    try:
      # FIXME: Permissions?
      # FIXME: Symbolic links?
      fp = tempfile.NamedTemporaryFile(mode='wb',
          prefix=os.path.basename(filename),
          dir=os.path.dirname(filename))
      # python2.5 does not have delete parameter:
      fp.unlink = lambda *args: None
      try:
        fp.writelines(modified)
        fp.close()
        if os.path.exists(filename):
          os.rename(filename, filename+'~')
        os.rename(fp.name, filename)
      finally:
        fp.close()
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
  if protos.intersection(['ssh','conf','localhost']):
    while newpass == '' or newpass != newpass1:
      newpass = getpass.getpass('new password: ')
      newpass1 = getpass.getpass('Confirm new password: ')

  for (proto, data) in urls:
    if proto in ('verifyssh', 'ssh'):
      (username, host) = data

    if proto == 'verifyssh':
      try:
        ui._cprint('bright yellow', 'Verifying password on %s...'%host)
        if verify_ssh_passwd(ui, host, username, oldpass):
          ui._cprint('bright green', 'Ok')
        else:
          ui._cprint('bright red', 'Failed!')
      except pexpect.TIMEOUT, e:
        ui._cprint('bright red', 'timeout')
      except _PasswordChangeException, e:
        ui._cprint('bright red', 'Exception verifying password on %s:'%(host, e))
      except Exception, e:
        import traceback
        ui._cprint('red', traceback.format_exc())
        ui._cprint('bright red', 'Exception verifying password on %s:'%(host, e))

    if proto == 'ssh':
      try:
        ui._cprint('bright yellow', 'Changing password on %s for user %s...'%(host, username))
        if change_ssh_passwd(ui, host, username, oldpass, newpass):
          ui._cprint('bright green', 'Success')
      except _PasswordChangeException, e:
        ui._cprint('bright red', 'Password change failed on %s: %s'%(host,e))
      except Exception, e:
        import traceback
        ui._cprint('red', traceback.format_exc())
        ui._cprint('bright red', 'Password change failed on %s: %s'%(host,e))

    if proto == 'localhost':
      try:
        if change_tty_passwd(ui, oldpass, newpass):
          ui._cprint('bright green', 'Success')
      except _PasswordChangeException, e:
        ui._cprint('bright red', 'Local password change failed: %s'%e)
      except Exception, e:
        import traceback
        ui._cprint('red', traceback.format_exc())
        ui._cprint('bright red', 'Local password change failed: %s'%e)

    if proto == 'conf':
      try:
        ui._cprint('bright yellow', 'Updating %s...'%data)
        update_config(ui, data, oldpass, newpass)
      except:
        ui._cprint('bright red', 'Updating configuration file failed!')

if __name__ == '__main__':
  import ui.ui_tty
  ui = ui.ui_tty()
  #test_expect_groups(ui)
  main(ui)
