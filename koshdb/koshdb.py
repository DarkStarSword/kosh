#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab

import os
import fcntl
import Crypto.Hash.SHA
import Crypto.Hash.SHA256
import Crypto.Cipher.AES
import base64

def randBits(size):
  import Crypto.Random
  return Crypto.Random.get_random_bytes(size/8)

class ChecksumFailure(Exception): pass

class _masterKey(object):
  # TODO: Add timeout
  # TODO: Protect self._key (mprotect, accessor methods)
  BLOB_PREFIX = 'k:'

  def __init__(self, passphrase, blob=None):
    if blob is None:
      self._key = randBits(256)
      self._blob = self._enc(self._key, passphrase)
    else:
      assert(blob.startswith(_masterKey.BLOB_PREFIX))
      self._blob = blob[len(_masterKey.BLOB_PREFIX):]
      self._key = self._dec(self._blob, passphrase)

  def __str__(self):
    return _masterKey.BLOB_PREFIX + self._blob

  @staticmethod
  def _enc(key, passphrase):
    h = Crypto.Hash.SHA256.new(passphrase).digest()
    s = randBits(256)
    k = ''.join([chr(ord(a) ^ ord(b)) for (a,b) in zip(h,s)])
    a = Crypto.Cipher.AES.new(k)
    checksum = Crypto.Hash.SHA256.new(key).digest()
    e = a.encrypt(key + checksum)
    return base64.encodestring(e+s).replace('\n','')

  @staticmethod
  def _dec(blob, passphrase):
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

class KoshDB(object):
  FILE_HEADER = 'K05Hv0 UNSTABLE\n'

  def __init__(self, filename, prompt):
    self.filename = filename
    passphrase = prompt('Enter master passphrase:')

    if os.path.isfile(filename):
      self._open(filename, passphrase, prompt)
    else:
      self._create(filename, passphrase, prompt)

  def _create(self, filename, passphrase, prompt):
    if prompt('Confirm master passphrase:') != passphrase:
      raise Exception('FIXME: passphrases do not match')
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
      fp.flush()
      if os.path.exists(filename):
        os.rename(filename, filename+'~')
      os.rename(fp.name, filename)

  def _open(self, filename, passphrase, prompt):
    self.fp = open(filename, 'rb')
    self._readExpect(KoshDB.FILE_HEADER)
    passphrases = set()
    passphrases.add(passphrase)
    self._masterKeys = []
    for line in self.fp:
      if line.startswith(_masterKey.BLOB_PREFIX):
        (key, passphrase) = self._unlockMasterKey(len(self._masterKeys), line, passphrases, prompt)
        self._masterKeys.append(key)
        passphrases.add(passphrase)

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
