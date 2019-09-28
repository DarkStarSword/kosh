#!/usr/bin/env python2.6
# vi:sw=2:ts=2:expandtab

# Copyright (C) 2009-2015 Ian Munsie
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

class ui_null(object):
  """
  Dummy class that will do nothing when called, and return itself as any of
  it's attributes.  Intended to be used in place of a ui class where no
  interaction is to take place. Calls such as ui_null().mainloop.foo.bar.baz()
  will not raise any exceptions.
  """
  def __call__(self, *args, **kwargs): pass
  def __getattribute__(self,name):
    return self

