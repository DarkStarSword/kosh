#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab:sts=2

# Copyright (C) 2025 Ian Munsie
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

import urllib

def try_totp(field):
  try:
    import pyotp
    # TODO: Newer pyotp has a built in URL parser that would be more
    # convenient to use, but want to support older versions
    result = urllib.parse.urlparse(field)
    if result.scheme != 'otpauth' or result.netloc != 'totp':
      return None
    query = urllib.parse.parse_qs(result.query)
    algorithm, = query.get('algorithm', ['SHA1'])
    digits, = map(int, query.get('digits', ['6']))
    period, = map(int, query.get('period', ['30']))
    secret, = query['secret']
    totp = pyotp.TOTP(secret, digits=digits, digest=algorithm, interval=period)
    return totp
  except:
    return None

def try_totp_str(field):
  totp = try_totp(field)
  if totp is not None:
    return totp.now()
  return field

def totp_iter(blobs):
  for (field, blob) in blobs:
    yield (field, try_totp_str(blob))
