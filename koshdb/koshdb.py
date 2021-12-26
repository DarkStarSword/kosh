#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab

# Copyright (C) 2009-2021 Ian Munsie
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

import os, sys
import fcntl, errno
import Crypto.Hash.SHA
import Crypto.Hash.SHA256
import Crypto.Cipher.AES
import Crypto.Util.strxor
import base64
import weakref
import json

def randBits(size):
  import Crypto.Random
  return Crypto.Random.get_random_bytes(size//8)

def extendstr(data, length):
  return (data*(length//len(data)+1))[:length]

class ChecksumFailure(Exception): pass
class KeyExpired(Exception): pass
class Bug(Exception): pass
class ReadOnlyPassEntry(Exception): pass
class FileLocked(Exception): pass

# FIXME: HACK to work with pwsafe imported files for now:
#passDefaultFieldOrder = ['Username','Password']
#passDefaultCopyFieldOrder = ['Username','Password']
passDefaultFieldOrder = ['Username','login','Password','passwd']
passDefaultCopyFieldOrder = ['Username','login','Password','passwd']

class _masterKey(object):
  # TODO: Protect self._key (mprotect, accessor methods)
  BLOB_PREFIX = b'k:'

  def __init__(self, passphrase, blob=None):
    if blob is None:
      self._key = randBits(256)
      self._blob = self._encMasterKey(self._key, passphrase)
    else:
      assert(blob.startswith(self.BLOB_PREFIX))
      self._blob = blob[len(self.BLOB_PREFIX):]
      self.unlock(passphrase)

  def unlock(self, passphrase):
    self._key = self._decMasterKey(self._blob, passphrase)

  def expire(self):
    """ MUST be called to clean up threads, otherwise the program will not terminate until timeout """
    try:
      del self._key
    except AttributeError:
      pass

  def __str__(self):
    return self.BLOB_PREFIX + self._blob

  def __setattr__(self, name, val):
    if name == '_key': self.expire()
    object.__setattr__(self, name, val)

  def __getattr__(self, name):
    if name == '_key':
      # Only called if _key is not present
      raise KeyExpired()
    raise AttributeError()

  def encrypt(self, data):
    """
    Take a chunk of data and encrypt it using this key.
    Raises KeyExpired if this key has timed out.
    """
    import Crypto.Util.strxor
    def pad(data, multiple):
      assert(multiple < 256)
      padding = multiple - ((len(data) + 1) % multiple)
      return data + '\0'*padding + chr(padding+1)
    checksum = Crypto.Hash.SHA.new(data).digest()
    a = Crypto.Cipher.AES.new(self._key)
    s = randBits(256)
    data = Crypto.Util.strxor.strxor(data,extendstr(s, len(data)))
    e = a.encrypt(pad(data + s + checksum, Crypto.Cipher.AES.block_size))
    return base64.encodebytes(e).replace('\n','')


  def decrypt(self, blob):
    """
    Take a base64 encoded and encrypted blob and attempt to decrypt it using this key.
    Raises ChecksumFailure if this key was not used to encrypt the blob.
    Raises KeyExpired if this key has timed out.
    """
    def unpad(data):
      padding = ord(data[-1:])
      return data[:-padding]
    d = base64.decodebytes(blob)
    a = Crypto.Cipher.AES.new(self._key)
    deciphered = unpad(a.decrypt(d))
    decrypted = deciphered[:-Crypto.Hash.SHA.digest_size-32]
    salt      = deciphered[-Crypto.Hash.SHA.digest_size-32:-Crypto.Hash.SHA.digest_size]
    checksum  = deciphered[-Crypto.Hash.SHA.digest_size:]
    decrypted = Crypto.Util.strxor.strxor(decrypted,extendstr(salt, len(decrypted)))
    if checksum != Crypto.Hash.SHA.new(decrypted).digest():
      raise ChecksumFailure()
    return decrypted

  @staticmethod
  def _encMasterKey(key, passphrase):
    h = Crypto.Hash.SHA256.new(passphrase.encode('utf8')).digest()
    s = randBits(256)
    k = Crypto.Util.strxor.strxor(h,s)
    a = Crypto.Cipher.AES.new(k)
    checksum = Crypto.Hash.SHA256.new(key).digest()
    e = a.encrypt(key + checksum)
    return base64.encodebytes(e+s).replace('\n','')

  @staticmethod
  def _decMasterKey(blob, passphrase):
    d = base64.decodebytes(blob)
    h = Crypto.Hash.SHA256.new(passphrase.encode('utf8')).digest()
    e = d[:-256//8]
    s = d[-256//8:]
    k = Crypto.Util.strxor.strxor(h,s)
    a = Crypto.Cipher.AES.new(k)
    deciphered = a.decrypt(e)
    key      = deciphered[:-Crypto.Hash.SHA256.digest_size]
    checksum = deciphered[-Crypto.Hash.SHA256.digest_size:]
    if checksum != Crypto.Hash.SHA256.new(key).digest():
      raise ChecksumFailure()
    return key

class passEntry(dict):
  BLOB_PREFIX = b'p:'

  def __init__(self, masterKey, blob=None, name=None):
    if type(masterKey) == weakref.ProxyType:
      self._masterKey = masterKey
    else:
      self._masterKey = weakref.proxy(masterKey)
    self._timestamp = None
    self.older = None
    self.newer = None
    self.meta = {}
    if blob is not None:
      assert(blob.startswith(self.BLOB_PREFIX))
      self._blob = blob[len(self.BLOB_PREFIX):]
      self._dec()
    elif name is not None:
      self.name = name
    else:
      self.name = ''

  def clone(self):
    import copy
    n = passEntry(self._masterKey, name=self.name)
    dict.__init__(n, self)
    n.meta = copy.copy(self.meta)
    n.meta['RenamedFrom'] = self.newest().name
    return n

  def newest(self):
    newest = self
    while newest.newer:
      newest = newest.newer
    return newest

  def __str__(self):
    return self.BLOB_PREFIX + self._blob

  def __setitem__(self, name, val):
    if self._timestamp is not None:
      raise ReadOnlyPassEntry()
    dict.__setitem__(self, name, val)
    self._enc()

  def __delitem__(self, name):
    dict.__delitem__(self, name)
    self._enc()

  def _enc(self):
    serialise = json.dumps((self.name, self._timestamp, self, self.meta))
    self._blob = self._masterKey.encrypt(serialise)

  def _dec(self):
    contents = self._masterKey.decrypt(self._blob)
    (self.name, self._timestamp, data, self.meta) = json.loads(contents)
    self.update(data)

  def timestamp(self):
    import time
    if self._timestamp is None:
      self._timestamp = int(time.time())
      self._enc()
    return self._timestamp

  def __cmp__(self, other):
    return cmp(self._timestamp, other._timestamp)

  def __ge__(self, other):
    return self._timestamp >= other._timestamp

  def __eq__(self, other):
    # Do not consider timestamp when checking for equality
    return self.name == other.name and dict.__eq__(self, other) and self.meta == other.meta

  def __ne__(self, other):
    return not passEntry.__eq__(self, other)

  def __iter__(self):
    """
    Return an iterator that will iterate over the fields in a sensible order.
    If the FieldOrder metadata is present in this entry that will be used to
    order the fields, otherwise a default ordering will be applied. Any fields
    that are not tagged to have a particular order will be returned after all
    ordered fields.
    """
    order = passDefaultFieldOrder
    if 'FieldOrder' in self.meta:
      order = self.meta['FieldOrder']

    def sortedGen(self, order):
      fields = list(self.keys())
      for field in order:
        if field in fields:
          yield field
          fields.remove(field)
      for field in fields:
        yield field

    return sortedGen(self, order)

  def clipIter(self):
    """
    Return an iterator that will iterate over the contents of the fields in an
    order suitable for passing to the X clipboard. This can be overridden on a
    per entry basis.
    """
    order = passDefaultCopyFieldOrder
    if 'CopyFieldOrder' in self.meta:
      order = self.meta['CopyFieldOrder']

    def sortedGen(self, order):
      fields = list(self.keys())
      for field in order:
        if field in fields:
          yield (field, self[field])

    return sortedGen(self, order)

class KoshDB(dict):
  FILE_HEADER = b'K05Hv0 UNSTABLE\n'

  def __init__(self, filename, prompt):
    self.filename = filename

    if os.path.isfile(filename):
      self._open(filename, prompt)
    else:
      self._create(filename, prompt)

  def __del__(self):
    if '_masterKeys' in self:
      for x in self._masterKeys:
        x.expire()

  def _create(self, filename, prompt):
    msg = 'New Password Database\nEnter passphrase:'
    failmsg = 'Passphrases do not match!\n\n'+msg
    while True:
      passphrase = prompt(msg)
      if prompt('Confirm passphrase:') == passphrase:
        break
      msg = failmsg
    masterKey = _masterKey(passphrase)
    self._masterKeys = [masterKey]
    self._oldEntries = []
    self._lines = [masterKey]
    self._write(filename)

  def write(self):
    self._write(self.filename)

  def _write(self, filename):
    # FIXME: Locking to avoid separate processes clobbering each other
    from tempfile import NamedTemporaryFile
    from copy import copy
    bug = False

    entries = copy(self._masterKeys) + list(self.values()) + copy(self._oldEntries)

    dirname = os.path.expanduser(os.path.dirname(filename))
    if not os.path.exists(dirname):
      os.makedirs(dirname, mode=0o700)
    with NamedTemporaryFile(mode='wb', delete=False,
        prefix=os.path.basename(filename),
        dir=dirname) as fp:

      fp.write(KoshDB.FILE_HEADER)

      for line in self._lines:
        if type(line) == type(''):
          fp.write(line)
        else:
          fp.write(str(line).strip() + '\n')
          try:
            entries.remove(line)
          except:
            bug = True
            fp.write("# WARNING: Above entry not found in masterkeys or password entries\n")

      if entries != []:
        bug = True
        fp.write("# WARNING: Below entries not tracked\n")
        for entry in entries:
          fp.write(str(entry).strip() + '\n')
        fp.write("# WARNING: Above entries not tracked\n")

      fp.flush()
      if os.path.exists(filename):
        os.rename(filename, filename+'~')
      os.rename(fp.name, filename)

      if bug:
        raise Bug("Refer to %s for details" % filename)

  def _open(self, filename, prompt):
    self.fp = open(filename, 'rb+') # Must open for write access for lock to succeed
    try:
      fcntl.lockf(self.fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError as e:
      if e.errno not in (errno.EACCES, errno.EAGAIN):
        raise
      # TODO: Allow read only access
      raise FileLocked()
    self._readExpect(KoshDB.FILE_HEADER)
    self._masterKeys = []
    self._lines = []
    self._oldEntries = []
    passphrase = prompt('Enter passphrase:')
    passphrases = set()
    passphrases.add(passphrase)
    for (idx, line) in enumerate(self.fp):
      if line.startswith(_masterKey.BLOB_PREFIX):
        (key, passphrase) = self._unlockMasterKey(len(self._masterKeys), line, passphrases, prompt)
        self._masterKeys.append(key)
        passphrases.add(passphrase)
        self._lines.append(key)
      elif line.startswith(passEntry.BLOB_PREFIX):
        for key in self._masterKeys:
          try:
            entry = passEntry(key, line)
          except ChecksumFailure:
            continue
          else:
            self[entry.name] = entry
            break
        else:
          # Multi user mode may ignore this
          raise ChecksumFailure()
      else:
        # Unrecognised entry - could be a comment, entry encoded by a different key, etc. whatever it is, don't lose it:
        self._lines.append(line)

  def __setitem__(self, name, val):
    assert(name == val.name)
    val.timestamp()
    if 'RenamedFrom' in val.meta:
      oldname = val.meta['RenamedFrom']
      if oldname == name:
        del val.meta['RenamedFrom']
    else:
      oldname = name
    # FIXME: there is an edge case I haven't handled where renamed or deleted
    # entries that have been stored out of order will not end up, so the old
    # names may show up. There is a related edge case of any out of order
    # entries causing the history to be out of order.
    # FIXME: Handle the edge case where one entry has been renamed over
    # another - it's valid, but be sure we don't lose the history of either
    # path
    if oldname in self:
      if self[oldname] == val:
        return
      (new, old) = self.resolveConflict(self[oldname], val)
      # FIXME: Bogus timestamp in future
      if 'RenamedFrom' in new.meta:
        # Don't use del or we will recurse:
        dict.__delitem__(self, old.name)
      if 'Deleted' in new.meta:
        # Don't use del or we will recurse:
        dict.__delitem__(self, old.name)
        self._oldEntries.append(new)
      else:
        dict.__setitem__(self, name, new)
      self._oldEntries.append(old)
    else:
      if 'Deleted' in val.meta:
        # Edge case - deleting a non-(yet?)-existant entry
        self._oldEntries.append(val)
      dict.__setitem__(self, name, val)
    self._lines.append(val)

  def __delitem__(self, item):
    n = self[item.name].clone()
    n.clear()
    n.meta = {'Deleted': True}
    self[item.name] = n

  @staticmethod
  def resolveConflict(entry1, entry2):
    (new,old) = [(entry1,entry2),(entry2,entry1)][entry2 >= entry1]
    new.older = old
    old.newer = new
    # FIXME: Ensure entire chain is sorted
    return (new, old)

  def _unlockMasterKey(self, idx, blob, passphrases, prompt):
    for passphrase in passphrases:
      try:
        key = _masterKey(passphrase, blob)
      except ChecksumFailure:
        pass
      else:
        return (key, passphrase)
    while True:
      passphrase = prompt('Passphrase error\n'
          'Enter master passphrase for key %i:' % (idx+1))
      try:
        key = _masterKey(passphrase, blob)
      except ChecksumFailure:
        continue
      else:
        return (key, passphrase)

  def _readExpect(self, expect):
    r = self.fp.read(len(expect))
    if (r != expect):
      raise Exception("Unrecognised file header")

  def _changeMasterPass(self, oldpass, newpass):
    raise Exception('unimplemented')

  def importEntry(self, entry):
    newE = passEntry(self._masterKeys[0])
    for k in entry:
      if k == 'name':
        newE.name = entry[k]
      else:
        newE[k] = entry[k]
    for e in self: # dict isn't hashable, so can't use in without implementing __hash__ in a reliable manner
      if newE == self[e]:
        return False
    if not newE.name:
      raise Exception('No name on imported entry, not importing')
    self[newE.name] = newE
    return True

if __name__ == '__main__':
  import tempfile
  filename = tempfile.mktemp()
  try:
    def prompt(*args):
      return 'foobar'
    db = KoshDB(filename, prompt)
    e = passEntry(db._masterKeys[0]) # FIXME: Doing this creates a strong reference to the master key - timers will not automatically be destroyed
    e['foo'] = 'bar'
    print(e._blob)

    d = passEntry(db._masterKeys[0], passEntry.BLOB_PREFIX + e._blob)
    print(d['foo'])
    del e
    del d
    del db
  finally:
    os.remove(filename)
