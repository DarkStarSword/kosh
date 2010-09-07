#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab

import os
import fcntl
import Crypto.Hash.SHA
import Crypto.Hash.SHA256
import Crypto.Cipher.AES
import base64
import threading
import weakref
import json

def randBits(size):
  import Crypto.Random
  return Crypto.Random.get_random_bytes(size/8)

class ChecksumFailure(Exception): pass
class KeyExpired(Exception): pass

class _masterKey(object):
  # TODO: Add timeout
  # TODO: Protect self._key (mprotect, accessor methods)
  BLOB_PREFIX = 'k:'
  TIMEOUT = 60

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

  def touch(self):
    self._timer = threading.Timer(self.TIMEOUT, self.expire)
    self._timer.start()

  def expire(self):
    """ MUST be called to clean up threads, otherwise the program will not terminate until timeout """
    if hasattr(self, '_timer'):
      self._timer.cancel()
      del self._timer
    if hasattr(self, '_key'):
      del self._key

  #def __del__(self):
  #  # Cancel any running timers in other threads
  #  self.expire()

  def __str__(self):
    return self.BLOB_PREFIX + self._blob

  def __setattr__(self, name, val):
    if name == '_key': self.expire()
    object.__setattr__(self, name, val)
    if name == '_key': self.touch()

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
    def pad(data, multiple):
      assert(multiple < 256)
      padding = multiple - ((len(data) + 1) % multiple)
      return data + '\0'*padding + chr(padding+1)
    a = Crypto.Cipher.AES.new(self._key)
    checksum = Crypto.Hash.SHA.new(data).digest()
    e = a.encrypt(pad(data + checksum, Crypto.Cipher.AES.block_size))
    return base64.encodestring(e).replace('\n','')


  def decrypt(self, blob):
    """
    Take a base64 encoded and encrypted blob and attempt to decrypt it using this key.
    Raises ChecksumFailure if this key was not used to encrypt the blob.
    Raises KeyExpired if this key has timed out.
    """
    def unpad(data):
      padding = ord(data[-1:])
      return data[:-padding]
    d = base64.decodestring(blob)
    a = Crypto.Cipher.AES.new(self._key)
    deciphered = unpad(a.decrypt(d))
    decrypted = deciphered[:-Crypto.Hash.SHA.digest_size]
    checksum  = deciphered[-Crypto.Hash.SHA.digest_size:]
    if checksum != Crypto.Hash.SHA.new(decrypted).digest():
      raise ChecksumFailure()
    return decrypted

  @staticmethod
  def _encMasterKey(key, passphrase):
    h = Crypto.Hash.SHA256.new(passphrase).digest()
    s = randBits(256)
    k = ''.join([chr(ord(a) ^ ord(b)) for (a,b) in zip(h,s)])
    a = Crypto.Cipher.AES.new(k)
    checksum = Crypto.Hash.SHA256.new(key).digest()
    e = a.encrypt(key + checksum)
    return base64.encodestring(e+s).replace('\n','')

  @staticmethod
  def _decMasterKey(blob, passphrase):
    d = base64.decodestring(blob)
    h = Crypto.Hash.SHA256.new(passphrase).digest()
    e = d[:-256/8]
    s = d[-256/8:]
    k = ''.join([chr(ord(a) ^ ord(b)) for (a,b) in zip(h,s)])
    a = Crypto.Cipher.AES.new(k)
    deciphered = a.decrypt(e)
    key      = deciphered[:-Crypto.Hash.SHA256.digest_size]
    checksum = deciphered[-Crypto.Hash.SHA256.digest_size:]
    if checksum != Crypto.Hash.SHA256.new(key).digest():
      raise ChecksumFailure()
    return key

class passEntry(dict):
  BLOB_PREFIX = 'p:'

  def __init__(self, masterKey, blob=None, name=None):
    self._masterKey = weakref.proxy(masterKey)
    if blob is not None:
      assert(blob.startswith(self.BLOB_PREFIX))
      self._blob = blob[len(self.BLOB_PREFIX):]
      contents = masterKey.decrypt(self._blob)
      decode = json.loads(contents)
      self.name = decode[0]
      self.update(decode[1])
    elif name is not None:
      self.name = name
    else:
      raise Exception('Need either a name or an encrypted blob')

  def __str__(self):
    return self.BLOB_PREFIX + self._blob

  def __setitem__(self, name, val):
    dict.__setitem__(self, name, val)
    self._enc()

  def __delitem__(self, name):
    dict.__delitem__(self, name)
    self._enc()

  def _enc(self):
    serialise = json.dumps((self.name, self))
    self._blob = self._masterKey.encrypt(serialise)
   

class KoshDB(dict):
  FILE_HEADER = 'K05Hv0 UNSTABLE\n'

  def __init__(self, filename, prompt):
    self.filename = filename

    if os.path.isfile(filename):
      self._open(filename, prompt)
    else:
      self._create(filename, prompt)

  def __del__(self):
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
    self._masterKeys = [_masterKey(passphrase)]
    self._write(filename)

  def _write(self, filename):
    # FIXME: Locking to avoid separate processes clobbering each other
    import tempfile
    with tempfile.NamedTemporaryFile(mode='wb', delete=False,
        prefix=os.path.basename(filename),
        dir=os.path.dirname(filename)) as fp:
      fp.write(KoshDB.FILE_HEADER)
      for key in self._masterKeys:
        fp.write(str(key) + '\n')
      for entry in self:
        fp.write(str(entry) + '\n')
      fp.flush()
      if os.path.exists(filename):
        os.rename(filename, filename+'~')
      os.rename(fp.name, filename)

  def _open(self, filename, prompt):
    self.fp = open(filename, 'rb')
    self._readExpect(KoshDB.FILE_HEADER)
    self._masterKeys = []
    passphrase = prompt('Enter passphrase:')
    passphrases = set()
    passphrases.add(passphrase)
    for line in self.fp:
      if line.startswith(_masterKey.BLOB_PREFIX):
        (key, passphrase) = self._unlockMasterKey(len(self._masterKeys), line, passphrases, prompt)
        self._masterKeys.append(key)
        passphrases.add(passphrase)
      elif line.startswith(passEntry.BLOB_PREFIX):
        for key in self._masterKeys:
          try:
            entry = passEntry(key, line)
          except ChecksumFailure:
            continue
          else:
            self[entry['name']] = entry
            break
        else:
          # Multi user mode may ignore this
          raise ChecksumFailure()

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

if __name__ == '__main__':
  import tempfile
  filename = tempfile.mktemp()
  try:
    def prompt(*args):
      return 'foobar'
    db = KoshDB(filename, prompt)
    e = passEntry(db._masterKeys[0]) # FIXME: Doing this creates a strong reference to the master key - timers will not automatically be destroyed
    e['foo'] = 'bar'
    print e._blob

    d = passEntry(db._masterKeys[0], passEntry.BLOB_PREFIX + e._blob)
    print d['foo']
    del e
    del d
    del db
  finally:
    os.remove(filename)
