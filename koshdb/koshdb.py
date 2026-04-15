#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab

# Copyright (C) 2009-2025 Ian Munsie
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
import errno
try:
  # Getting a bit sick of packages that never heard of backwards compatibility...
  import Cryptodome.Hash.SHA
  import Cryptodome.Hash.SHA256
  import Cryptodome.Cipher.AES
  import Cryptodome.Util.strxor
  Crypto = Cryptodome
except ImportError:
  import Crypto.Hash.SHA
  import Crypto.Hash.SHA256
  import Crypto.Cipher.AES
  import Crypto.Util.strxor
import base64
import weakref
import json

def randBits(size):
  return os.urandom(size//8)

def extendstr(data, length):
  return (data*(length//len(data)+1))[:length]

class ChecksumFailure(Exception): pass
class KeyExpired(Exception): pass
class Bug(Exception): pass
class ReadOnlyPassEntry(Exception): pass
class FileLocked(Exception): pass
class ReadOnlySourceError(Exception): pass

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
    raise NotImplemented('python3')
  def __bytes__(self):
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
    def pad(data, multiple):
      assert(multiple < 256)
      padding = multiple - ((len(data) + 1) % multiple)
      return data + b'\0'*padding + bytes([padding+1])
    data = data.encode('utf8')
    checksum = Crypto.Hash.SHA.new(data).digest()
    try:
      a = Crypto.Cipher.AES.new(self._key)
    except TypeError:
      # pycryptodome changed function signature to pass mode. Using ECB for
      # backwards compatibility. FIXME: Upgrade db to something stronger?
      a = Crypto.Cipher.AES.new(self._key, mode=Crypto.Cipher.AES.MODE_ECB)
    s = randBits(256)
    data = Crypto.Util.strxor.strxor(data,extendstr(s, len(data)))
    e = a.encrypt(pad(data + s + checksum, Crypto.Cipher.AES.block_size))
    return base64.encodebytes(e).replace(b'\n',b'')


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
    try:
      a = Crypto.Cipher.AES.new(self._key)
    except TypeError:
      # pycryptodome changed function signature to pass mode. Using ECB for
      # backwards compatibility. FIXME: Upgrade db to something stronger?
      a = Crypto.Cipher.AES.new(self._key, mode=Crypto.Cipher.AES.MODE_ECB)
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
    try:
      a = Crypto.Cipher.AES.new(k)
    except TypeError:
      # pycryptodome changed function signature to pass mode. Using ECB for
      # backwards compatibility. FIXME: Upgrade db to something stronger?
      a = Crypto.Cipher.AES.new(k, mode=Crypto.Cipher.AES.MODE_ECB)
    checksum = Crypto.Hash.SHA256.new(key).digest()
    e = a.encrypt(key + checksum)
    return base64.encodebytes(e+s).replace(b'\n',b'')

  def reencrypt(self, new_passphrase):
    """Create a new _masterKey encrypting the same underlying key with a new passphrase."""
    new_mk = _masterKey.__new__(_masterKey)
    new_mk._key = self._key  # __setattr__ calls expire() on new_mk first (no-op on fresh object)
    new_mk._blob = _masterKey._encMasterKey(self._key, new_passphrase)
    return new_mk

  @staticmethod
  def _decMasterKey(blob, passphrase):
    d = base64.decodebytes(blob)
    h = Crypto.Hash.SHA256.new(passphrase.encode('utf8')).digest()
    e = d[:-256//8]
    s = d[-256//8:]
    k = Crypto.Util.strxor.strxor(h,s)
    try:
      a = Crypto.Cipher.AES.new(k)
    except TypeError:
      # pycryptodome changed function signature to pass mode. Using ECB for
      # backwards compatibility. FIXME: Upgrade db to something stronger?
      a = Crypto.Cipher.AES.new(k, mode=Crypto.Cipher.AES.MODE_ECB)
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

  def history(self):
    node = self
    while node is not None:
      yield node
      node = node.older

  def __str__(self):
    raise NotImplemented('python3')
  def __bytes__(self):
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
      found = False
      for field in order:
        if field in fields:
          yield (field, self[field])
          found = True
      # If no fields are in CopyFieldOrder, use DisplayOrder instead:
      if not found:
        for field in iter(self):
          yield (field, self[field])

    return sortedGen(self, order)

class KeySource:
  """
  Represents a potential key source discovered during a database scan.

  Designed to be extensible for future key types beyond passphrase
  (e.g. FIDO2/hardware tokens).  The source_type field indicates what
  kind of credential is needed to unlock this source.
  """
  TYPE_PASSPHRASE  = 'passphrase'   # standard k: blob, unlocked with a passphrase string
  TYPE_UNAVAILABLE = 'unavailable'  # redirect target that could not be read

  def __init__(self, source_type, source_file, blob=None, lineno=0, error=None):
    self.source_type = source_type
    self.source_file  = source_file  # the file this was found in
    self.blob    = blob     # raw k: line bytes  (TYPE_PASSPHRASE only)
    self.lineno  = lineno   # line number within source_file
    self.error   = error    # human-readable error (TYPE_UNAVAILABLE only)

  def try_unlock(self, credential):
    """
    Attempt to decrypt the key blob using the provided credential.
    For TYPE_PASSPHRASE, credential is a passphrase string.
    Returns a _masterKey object on success.
    Raises ChecksumFailure if the credential is wrong.
    """
    if self.source_type == self.TYPE_PASSPHRASE:
      return _masterKey(credential, self.blob)
    raise ValueError('Cannot unlock key source of type %r' % self.source_type)


class KoshDB(dict):
  FILE_HEADER = b'K05Hv0 UNSTABLE\n'
  REDIRECT_PREFIX = b'r:'

  def __init__(self, filename, prompt, key_files=None, key_file_prompt=None,
               unlock_prompt=None):
    self.filename = filename
    self.lock_fp = None
    self._current_source = None  # Tracks which file is being read, for line source attribution
    self._explicit_key_files = list(key_files) if key_files else []
    self._key_file_prompt = key_file_prompt  # optional: (error=None) -> (path, remember)
    self._unlock_prompt = unlock_prompt  # optional: new unified unlock dialog
    self._unresolved_p_lines = []  # p: lines buffered when no master key was yet available
    self._readonly_sources = set()  # sources that must not be written back (e.g. Windows paths)

    if os.path.isfile(filename):
      self._open(filename, prompt)
    else:
      self._create(filename, prompt)

  def __del__(self):
    if '_masterKeys' in self:
      for x in self._masterKeys:
        x.expire()
    if self.lock_fp is not None:
      self.lock_fp.close()
      os.remove(self.lock_fp.name)

  @staticmethod
  def _get_key_files(db_filename):
    """Find all *.key files in the same directory as the database."""
    import glob as glob_module
    dirpath = os.path.dirname(os.path.abspath(db_filename))
    pattern = os.path.join(dirpath, '*.key')
    key_files = sorted(glob_module.glob(pattern))
    # Don't re-read the main database file if it happens to end in .key
    abs_db = os.path.abspath(db_filename)
    return [f for f in key_files if os.path.abspath(f) != abs_db]

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
    # New databases use split files: master key goes in a separate .key file
    key_filename = filename + '.key'
    self._lines = [(masterKey, key_filename)]
    self._write(filename)

  def write(self):
    self._write(self.filename)

  def _write(self, filename):
    # FIXME: Locking to avoid separate processes clobbering each other
    from tempfile import NamedTemporaryFile
    from copy import copy
    bug = False

    entries = copy(self._masterKeys) + list(self.values()) + copy(self._oldEntries)

    # Group lines by source file, preserving within-file order.
    # Skip readonly sources (e.g. Windows paths read via cmd.exe) — they cannot
    # be written back from Linux and their content is reconstructed on each open.
    # Also remove any non-bytes objects from those skipped lines from entries so
    # they don't cause AttributeError when passEntry.__eq__ encounters a masterKey
    # during entries.remove() below.
    sources = {}
    for (line, source) in self._lines:
      if source in self._readonly_sources:
        if type(line) != type(b''):
          try:
            entries.remove(line)
          except ValueError:
            pass
        continue
      if source not in sources:
        sources[source] = []
      sources[source].append(line)

    # Ensure the main file is always written (even if it has no entries yet)
    if filename not in sources:
      sources[filename] = []

    # Write a temp file for each source
    temp_names = {}
    for source, lines in sources.items():
      source_dirname = os.path.dirname(os.path.abspath(source))
      if not os.path.exists(source_dirname):
        os.makedirs(source_dirname, mode=0o700)
      with NamedTemporaryFile(mode='wb', delete=False,
          prefix=os.path.basename(source),
          dir=source_dirname) as fp:

        fp.write(KoshDB.FILE_HEADER)

        for line in lines:
          if type(line) == type(b''):
            fp.write(line)
          else:
            fp.write(bytes(line).strip() + b'\n')
            try:
              entries.remove(line)
            except:
              bug = True
              fp.write(b"# WARNING: Above entry not found in masterkeys or password entries\n")

        fp.flush()
        fp.close()
        temp_names[source] = fp.name

    # Any entries not accounted for by _lines get appended to the main file
    if entries != []:
      bug = True
      with open(temp_names[filename], 'ab') as fp:
        fp.write(b"# WARNING: Below entries not tracked\n")
        for entry in entries:
          fp.write(bytes(entry).strip() + b'\n')
        fp.write(b"# WARNING: Above entries not tracked\n")

    # Atomically rename temp files to their targets.
    # Write key files first, main file last (main file holds the lock).
    for source, temp_name in temp_names.items():
      if source == filename:
        continue
      if os.path.exists(source):
        if os.path.exists(source + '~'):
          os.remove(source + '~')
        os.rename(source, source + '~')
      os.rename(temp_name, source)

    # Now rename the main file (close existing fp first so Windows can rename it)
    if hasattr(self, 'fp'):
      self.fp.close()
    if os.path.exists(filename):
      if os.path.exists(filename + '~'):
        os.remove(filename + '~')
      os.rename(filename, filename + '~')
    os.rename(temp_names[filename], filename)

    # Ensure we (still) have the db locked:
    self._open_and_lock(filename)

    if bug:
      raise Bug("Refer to %s for details" % filename)

  def _open_and_lock(self, filename):
    self.fp = open(filename, 'rb+') # Must open for write access for lock to succeed
    try:
      import fcntl
      fcntl.lockf(self.fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError as e:
      if e.errno not in (errno.EACCES, errno.EAGAIN):
        raise
      # TODO: Allow read only access
      raise FileLocked()
    except ImportError:
      # Windows doesn't have fcntl. Ideally we would just not pass
      # FILE_SHARE_READ when opening the database, but that would need to go
      # through too much win32api. Fall back to using a separate lock file:
      if self.lock_fp is None:
        try:
          lock_filename = filename+'.lock'
          if os.path.exists(lock_filename):
            # Try deleting it in case it's just stale. Since this is Windows only
            # code, this remove will fail if another instance still has it open.
            # Note that this would not be a good idea on most other platforms.
            os.remove(lock_filename)
          self.lock_fp = open(lock_filename, 'x') # Exclusive create mode
          self.lock_fp.write(str(os.getpid()))
          self.lock_fp.flush()
        except (FileExistsError, PermissionError):
          raise FileLocked()

  # -------------------------------------------------------------------------
  # Key-source scanning (no passphrase/decryption; just discovers k: blobs)
  # -------------------------------------------------------------------------

  def _scan_fp_for_key_sources(self, fp, source, visited):
    """Scan lines from a file-like object, collecting KeySource descriptors."""
    sources = []
    for lineno, line in enumerate(fp):
      if line.startswith(_masterKey.BLOB_PREFIX):
        sources.append(KeySource(KeySource.TYPE_PASSPHRASE, source,
                                 blob=line, lineno=lineno))
      elif line.startswith(self.REDIRECT_PREFIX):
        redirect_path = line[len(self.REDIRECT_PREFIX):].decode('utf-8', errors='replace').strip()
        if redirect_path:
          expanded = os.path.expanduser(redirect_path)
          abs_path  = os.path.abspath(expanded)
          if abs_path not in visited:
            visited.add(abs_path)
            sources.extend(self.scan_key_file(expanded, visited))
    return sources

  def scan_key_file(self, path, visited=None):
    """
    Scan a single key file and return a list of KeySource descriptors.
    Public so the unlock dialog can call it when the user adds a file path.
    visited: set of already-scanned abs paths for cycle prevention.
    """
    import io
    if visited is None:
      visited = set()
    (data, error) = self._try_read_file(path)
    if data is None:
      return [KeySource(KeySource.TYPE_UNAVAILABLE, path, error=error)]
    header_len = len(KoshDB.FILE_HEADER)
    if data[:header_len] != KoshDB.FILE_HEADER:
      return [KeySource(KeySource.TYPE_UNAVAILABLE, path,
                        error='Not a valid kosh key file')]
    return self._scan_fp_for_key_sources(io.BytesIO(data[header_len:]), path, visited)

  def _scan_key_sources(self, filename):
    """
    Scan all auto-discovered key file locations for KeySource descriptors.
    Returns (key_sources, visited_set).  Leaves self.fp positioned just
    after the file header, ready for the full read phase.
    """
    key_sources = []
    visited = set()
    visited.add(os.path.abspath(filename))

    for kf in self._explicit_key_files:
      expanded = os.path.expanduser(kf)
      abs_path  = os.path.abspath(expanded)
      if abs_path not in visited:
        visited.add(abs_path)
        key_sources.extend(self.scan_key_file(expanded, visited))

    for kf in self._get_key_files(filename):
      abs_path = os.path.abspath(kf)
      if abs_path not in visited:
        visited.add(abs_path)
        key_sources.extend(self.scan_key_file(kf, visited))

    # Scan main db for k: entries (legacy single-file databases store k: here)
    self.fp.seek(len(KoshDB.FILE_HEADER))
    key_sources.extend(self._scan_fp_for_key_sources(self.fp, filename, visited))
    self.fp.seek(len(KoshDB.FILE_HEADER))  # reset for full read phase

    return key_sources, visited

  # -------------------------------------------------------------------------

  def _read_lines_from_fp(self, fp, source, passphrases, prompt, visited):
    """Read and process all lines from an open file pointer."""
    self._current_source = source
    for lineno, line in enumerate(fp):
      if line.startswith(_masterKey.BLOB_PREFIX):
        (key, passphrase) = self._unlockMasterKey(source, lineno, line, passphrases, prompt)
        self._masterKeys.append(key)
        passphrases.add(passphrase)
        self._lines.append((key, source))
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
          # No key could decrypt this entry yet; buffer it for a second attempt
          # once all key sources have been loaded (handles split databases where
          # the key file is discovered after the main db is read, and the
          # no-key-found interactive prompt).
          # Store a placeholder in _lines at this position so that when the entry
          # is later resolved it can be put back in file order, preserving the
          # relative positions of comment and other unrecognised lines.
          placeholder_idx = len(self._lines)
          self._lines.append((line, source))
          self._unresolved_p_lines.append((line, source, placeholder_idx))
      elif line.startswith(self.REDIRECT_PREFIX):
        # r: lines point to additional key files (e.g. on a USB stick).
        # They are preserved verbatim and followed immediately.
        self._lines.append((line, source))
        redirect_path = line[len(self.REDIRECT_PREFIX):].decode('utf-8', errors='replace').strip()
        if redirect_path:
          expanded = os.path.expanduser(redirect_path)
          abs_path = os.path.abspath(expanded)
          if abs_path not in visited:
            self._follow_redirect(expanded, abs_path, passphrases, prompt, visited)
      else:
        # Unrecognised entry - could be a comment, entry encoded by a different key, etc. whatever it is, don't lose it:
        self._lines.append((line, source))
    self._current_source = None

  @staticmethod
  def _is_windows_path(path):
    """Return True if path looks like a Windows absolute path (drive letter or UNC)."""
    import re
    return bool(re.match(r'^[A-Za-z]:\\', path) or path.startswith('\\\\'))

  @staticmethod
  def _try_read_file(path):
    """
    Attempt to read a file, with a WSL2 cmd.exe fallback for Windows paths.
    Returns (data_bytes, error_str): data is None on failure, error is None on success.
    """
    import subprocess, version
    try:
      with open(path, 'rb') as f:
        return (f.read(), None)
    except (IOError, OSError) as e:
      if version.is_wsl() and KoshDB._is_windows_path(path):
        try:
          result = subprocess.run(
            ['cmd.exe', '/C', 'type', path],
            capture_output=True,
            timeout=5,
          )
          if result.returncode == 0 and result.stdout:
            return (result.stdout, None)
          return (None, 'cmd.exe could not read %s' % path)
        except (OSError, subprocess.TimeoutExpired) as ce:
          return (None, 'cmd.exe fallback failed for %s:\n%s' % (path, ce))
      return (None, str(e))

  def _follow_redirect(self, path, abs_path, passphrases, prompt, visited):
    """Follow an r: redirect to another key file; silently skip if unavailable."""
    import io
    (data, _err) = self._try_read_file(path)
    if data is not None:
      header_len = len(KoshDB.FILE_HEADER)
      if data[:header_len] == KoshDB.FILE_HEADER:
        visited.add(abs_path)
        if self._is_windows_path(path):
          self._readonly_sources.add(path)
        self._read_lines_from_fp(io.BytesIO(data[header_len:]), path, passphrases, prompt, visited)

  def _resolve_p_lines(self):
    """Attempt to decrypt p: lines that were buffered due to no available master key."""
    remaining = []
    for (line, source, placeholder_idx) in self._unresolved_p_lines:
      for key in self._masterKeys:
        try:
          entry = passEntry(key, line)
        except ChecksumFailure:
          continue
        else:
          self._current_source = source
          prev_len = len(self._lines)
          self[entry.name] = entry
          if len(self._lines) > prev_len:
            # __setitem__ appended one entry; move it to the placeholder position
            # so the resolved entry sits in the same file position as the original
            # raw bytes, preserving the order of comment and unrecognised lines.
            self._lines[placeholder_idx] = self._lines.pop()
          else:
            # __setitem__ returned early (e.g. identical duplicate); the placeholder
            # raw bytes at placeholder_idx are harmless — they'll be written back
            # as-is, which is equivalent to the original unmodified line.
            pass
          self._current_source = None
          break
      else:
        remaining.append((line, source, placeholder_idx))
    self._unresolved_p_lines = remaining

  def _open(self, filename, prompt):
    self._open_and_lock(filename)
    self._readExpect(KoshDB.FILE_HEADER)
    self._masterKeys = []
    self._lines = []
    self._oldEntries = []
    self._unresolved_p_lines = []
    self._readonly_sources = set()

    if self._unlock_prompt is not None:
      self._open_with_unlock_dialog(filename, prompt)
    else:
      self._open_legacy(filename, prompt)

  def _open_with_unlock_dialog(self, filename, prompt):
    """
    New open flow: scan key sources, show unified unlock dialog, full read.
    """
    # Phase 1 — scan all known key file locations; no passphrase required.
    (key_sources, _scan_visited) = self._scan_key_sources(filename)

    # Phase 2 — show unlock dialog; loop until at least one key is unlocked
    # or the user cancels.  The dialog validates credentials itself via
    # KeySource.try_unlock() and only returns once at least one succeeds.
    passphrases = set()
    extra_key_files = []   # user-added paths not saved as redirects

    result = self._unlock_prompt(key_sources, self.scan_key_file)
    if result is None:
      return  # user cancelled

    (unlock_pairs, added_files) = result

    # Collect validated passphrases so the full-read phase can decrypt
    # k: entries without re-prompting.
    for (ks, credential) in unlock_pairs:
      passphrases.add(credential)

    # Save any requested redirects BEFORE the full read so that
    # _get_key_files picks up the new <db>-redir.key file.
    for (path, remember) in added_files:
      expanded = os.path.expanduser(path)
      if self._is_windows_path(expanded):
        self._readonly_sources.add(expanded)
      if remember:
        self._save_redirect(filename, path)
      else:
        extra_key_files.append(expanded)

    # Phase 3 — full read: populate _lines, _masterKeys, passEntries.
    # Use a fresh visited set so all files are read into _lines.
    visited = set()
    visited.add(os.path.abspath(filename))

    # Read explicit (--keyfile) and user-added files via _try_read_file so that
    # Windows paths (possible for user-added files) work via the cmd.exe fallback.
    import io as _io
    for key_filename in self._explicit_key_files + extra_key_files:
      expanded = os.path.expanduser(key_filename)
      abs_path = os.path.abspath(expanded)
      if abs_path in visited:
        continue
      visited.add(abs_path)
      (data, _err) = self._try_read_file(expanded)
      if data is None:
        continue
      header_len = len(KoshDB.FILE_HEADER)
      if data[:header_len] != KoshDB.FILE_HEADER:
        continue
      if self._is_windows_path(expanded):
        self._readonly_sources.add(expanded)
      self._read_lines_from_fp(_io.BytesIO(data[header_len:]), expanded, passphrases, prompt, visited)

    for key_filename in self._get_key_files(filename):
      abs_path = os.path.abspath(key_filename)
      if abs_path in visited:
        continue
      visited.add(abs_path)
      try:
        with open(key_filename, 'rb') as kfp:
          header = kfp.read(len(KoshDB.FILE_HEADER))
          if header != KoshDB.FILE_HEADER:
            continue
          self._read_lines_from_fp(kfp, key_filename, passphrases, prompt, visited)
      except (IOError, OSError):
        pass

    self._read_lines_from_fp(self.fp, filename, passphrases, prompt, visited)

    if self._unresolved_p_lines:
      if self._masterKeys:
        self._resolve_p_lines()
      if self._unresolved_p_lines:
        raise ChecksumFailure()

  def _open_legacy(self, filename, prompt):
    """
    Original open flow (used when no unlock_prompt is provided).
    Kept for backward compatibility and non-GUI use.
    """
    passphrase = prompt('Enter passphrase:')
    passphrases = set()
    passphrases.add(passphrase)

    visited = set()
    visited.add(os.path.abspath(filename))

    for key_filename in self._explicit_key_files:
      expanded = os.path.expanduser(key_filename)
      abs_path = os.path.abspath(expanded)
      if abs_path in visited:
        continue
      visited.add(abs_path)
      try:
        with open(expanded, 'rb') as kfp:
          header = kfp.read(len(KoshDB.FILE_HEADER))
          if header != KoshDB.FILE_HEADER:
            continue
          self._read_lines_from_fp(kfp, expanded, passphrases, prompt, visited)
      except (IOError, OSError):
        pass

    for key_filename in self._get_key_files(filename):
      abs_path = os.path.abspath(key_filename)
      if abs_path in visited:
        continue
      visited.add(abs_path)
      try:
        with open(key_filename, 'rb') as kfp:
          header = kfp.read(len(KoshDB.FILE_HEADER))
          if header != KoshDB.FILE_HEADER:
            continue
          self._read_lines_from_fp(kfp, key_filename, passphrases, prompt, visited)
      except (IOError, OSError):
        pass

    self._read_lines_from_fp(self.fp, filename, passphrases, prompt, visited)

    if not self._masterKeys:
      self._request_key_file(filename, passphrases, prompt, visited)

    if self._unresolved_p_lines:
      if self._masterKeys:
        self._resolve_p_lines()
      if self._unresolved_p_lines:
        raise ChecksumFailure()

  def _request_key_file(self, db_filename, passphrases, prompt, visited):
    """Prompt the user for a key file when none was found automatically."""
    error = None
    while not self._masterKeys:
      if self._key_file_prompt is not None:
        result = self._key_file_prompt(error=error)
      else:
        msg = 'No master key found.\nEnter path to key file\n(leave empty to cancel):'
        if error:
          msg = error + '\n\n' + msg
        path = prompt(msg)
        result = (path.strip(), False) if path and path.strip() else None

      if not result or not result[0]:
        return  # User cancelled

      (path, remember) = result
      expanded = os.path.expanduser(path)
      abs_path = os.path.abspath(expanded)

      if abs_path in visited:
        error = 'Already loaded: ' + expanded
        continue

      import io
      (data, read_error) = self._try_read_file(expanded)
      if data is None:
        error = 'Could not open %s:\n%s' % (expanded, read_error)
        continue
      header_len = len(KoshDB.FILE_HEADER)
      if data[:header_len] != KoshDB.FILE_HEADER:
        error = 'Not a valid kosh key file:\n' + expanded
        continue
      visited.add(abs_path)
      if self._is_windows_path(expanded):
        self._readonly_sources.add(expanded)
      self._read_lines_from_fp(io.BytesIO(data[header_len:]), expanded, passphrases, prompt, visited)

      if not self._masterKeys:
        error = 'No master key found in:\n' + expanded
        continue

      if remember:
        self._save_redirect(db_filename, path)

  def _save_redirect(self, db_filename, key_path):
    """Store an r: redirect in a -redir.key file for future auto-discovery."""
    key_filename = db_filename + '-redir.key'
    redirect_line = (self.REDIRECT_PREFIX.decode() + key_path.strip() + '\n').encode('utf-8')
    self._lines.append((redirect_line, key_filename))
    # Write immediately so the redirect persists even if the user makes no other changes.
    self._write_key_file(key_filename)

  def _write_key_file(self, key_filename):
    """Write one key file to disk immediately (used during startup, bypasses normal write path)."""
    from tempfile import NamedTemporaryFile
    dirname = os.path.dirname(os.path.abspath(key_filename))
    if not os.path.exists(dirname):
      os.makedirs(dirname, mode=0o700)
    lines_for_file = [item for (item, src) in self._lines if src == key_filename]
    with NamedTemporaryFile(mode='wb', delete=False,
        prefix=os.path.basename(key_filename),
        dir=dirname) as tmp:
      tmp.write(KoshDB.FILE_HEADER)
      for line in lines_for_file:
        if isinstance(line, bytes):
          tmp.write(line)
        else:
          tmp.write(bytes(line).strip() + b'\n')
      tmp.flush()
      tmp.close()
    if os.path.exists(key_filename):
      if os.path.exists(key_filename + '~'):
        os.remove(key_filename + '~')
      os.rename(key_filename, key_filename + '~')
    os.rename(tmp.name, key_filename)

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
    # Track which file this entry belongs to; new entries go to the main db file
    source = self._current_source if self._current_source is not None else self.filename
    self._lines.append((val, source))

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

  def _unlockMasterKey(self, source, lineno, blob, passphrases, prompt):
    for passphrase in passphrases:
      try:
        key = _masterKey(passphrase, blob)
      except ChecksumFailure:
        pass
      else:
        return (key, passphrase)
    while True:
      linestr = ''
      if lineno != 0:
        linestr = ':%i' % lineno
      passphrase = prompt('Passphrase error\n'
          'Enter passphrase for %s%s:' % (source, linestr))
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

  def change_passphrase(self, new_passphrase):
    """Re-encrypt all master keys with a new passphrase, preserving their source files."""
    # Find which sources hold master key objects
    key_sources = {src for (item, src) in self._lines if isinstance(item, _masterKey)}
    readonly_key_sources = key_sources & self._readonly_sources
    if readonly_key_sources:
      raise ReadOnlySourceError(
        'Cannot change passphrase: master key is in a read-only source '
        '(Windows path):\n' + '\n'.join(sorted(readonly_key_sources))
      )
    new_keys = [key.reencrypt(new_passphrase) for key in self._masterKeys]
    key_map = {id(old): new for old, new in zip(self._masterKeys, new_keys)}
    self._lines = [(key_map.get(id(item), item), src) for (item, src) in self._lines]
    for key in self._masterKeys:
      key.expire()
    self._masterKeys = new_keys

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
