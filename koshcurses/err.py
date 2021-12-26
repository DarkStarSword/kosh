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

def showErr(msg):
  try:
    import urwid
    lb = urwid.ListBox(
        urwid.SimpleListWalker([ urwid.Text(msg) ]))

    def exit_on_q(input):
      if input in ['enter', 'q', 'Q', 'esc']:
        raise urwid.ExitMainLoop()
    urwid.MainLoop(lb, unhandled_input = exit_on_q).run()
  finally:
    print msg
