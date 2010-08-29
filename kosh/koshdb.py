#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab

import os
import fcntl
import Crypto.Hash.SHA256
import Crypto.Cipher.AES
import base64

def randBits(size):
  import Crypto.Random
  return Crypto.Random.get_random_bytes(size/8)


class KoshDB(object):
  FILE_HEADER = 'K05Hv0 UNSTABLE\n'

	def __init__(self, filename, masterPass):
    self.filename = filename
    self._masterPass = masterPass #prompt

    if os.path.isfile(filename):
      self._open(filename)
    else:
      self._create(filename)

  def _create(self, filename):
    self._masterKey = randBits(256)
    #self._masterPass = prompt
    self._write(filename)

  def _write(self, filename):
    import tempfile
    with tempfile.NamedTemporaryFile(mode='wb', delete=False,
        prefix=os.path.basename(filename),
        dir=os.path.dirname(filename)) as fp:
      fp.write(KoshDB.FILE_HEADER)
      fp.write('k:' + self._encMasterKey());
      fp.write('\n')
      fp.flush()
      if os.path.exists(filename):
        os.rename(filename, filename+'~')
      os.rename(fp.name, filename)

  def _open(self, filename):
    self.fp = open(filename, 'rb')
    fcntl.lockf(self.fp, fcntl.LOCK_SH)
    self._readExpect(KoshDB.FILE_HEADER)
    keys = []
    for l in self.fp:
      if l.startswith('k:'):
        keys.append(self._decMasterKey(l[2:]))

  def _readExpect(self, expect):
    r = self.fp.read(len(expect))
    if (r != expect):
      raise Exception("Unrecognised file header")

  def _changeMasterPass(self, oldpass, newpass):
    raise Exception('unimplemented')

  def _encMasterKey(self):
    h = Crypto.Hash.SHA256.new(self._masterPass).digest()
    s = randBits(256)
    k = ''.join([chr(ord(a) ^ ord(b)) for (a,b) in zip(h,s)])
    a = Crypto.Cipher.AES.new(k)
    e = a.encrypt(self._masterKey)
    return base64.encodestring(e+s).replace('\n','')

  def _decMasterKey(self, ciphertext):
    d = base64.decodestring(ciphertext)
    p = 'foobar' #Fixme: prompt
    h = Crypto.Hash.SHA256.new(p).digest()
    e = d[:32]
    s = d[32:]
    k = ''.join([chr(ord(a) ^ ord(b)) for (a,b) in zip(h,s)])
    a = Crypto.Cipher.AES.new(k)
    return a.decrypt(e)
