#!/usr/bin/env python
# -*- coding: utf-8 -*- For utf-8 'Box Drawing' symbols.
# vi:sw=2:ts=2:expandtab

import urwid
import weakref

# NOTE: Only some usable in curses, presumably depends on code page
# FIXME: Reduce set and fallback to standard ASCII symbols if it would fail
#        (I haven't reached a moment of clarity on understanding these
#        terminal encodings yet, and will not do this item until then. i.e. why
#        do any work at all? None of these are in 7 bit ASCII so none should be
#        encodable into ASCII)
utf_8_sequences = {
  'BOX DRAWINGS LIGHT HORIZONTAL'                         : '\xe2\x94\x80', # works
  'BOX DRAWINGS HEAVY HORIZONTAL'                         : '\xe2\x94\x81',
  'BOX DRAWINGS LIGHT VERTICAL'                           : '\xe2\x94\x82', # works
  'BOX DRAWINGS HEAVY VERTICAL'                           : '\xe2\x94\x83',
  'BOX DRAWINGS LIGHT TRIPLE DASH HORIZONTAL'             : '\xe2\x94\x84',
  'BOX DRAWINGS HEAVY TRIPLE DASH HORIZONTAL'             : '\xe2\x94\x85',
  'BOX DRAWINGS LIGHT TRIPLE DASH VERTICAL'               : '\xe2\x94\x86',
  'BOX DRAWINGS HEAVY TRIPLE DASH VERTICAL'               : '\xe2\x94\x87',
  'BOX DRAWINGS LIGHT QUADRUPLE DASH HORIZONTAL'          : '\xe2\x94\x88',
  'BOX DRAWINGS HEAVY QUADRUPLE DASH HORIZONTAL'          : '\xe2\x94\x89',
  'BOX DRAWINGS LIGHT QUADRUPLE DASH VERTICAL'            : '\xe2\x94\x8a',
  'BOX DRAWINGS HEAVY QUADRUPLE DASH VERTICAL'            : '\xe2\x94\x8b',
  'BOX DRAWINGS LIGHT DOWN AND RIGHT'                     : '\xe2\x94\x8c',
  'BOX DRAWINGS DOWN LIGHT AND RIGHT HEAVY'               : '\xe2\x94\x8d',
  'BOX DRAWINGS DOWN HEAVY AND RIGHT LIGHT'               : '\xe2\x94\x8e',
  'BOX DRAWINGS HEAVY DOWN AND RIGHT'                     : '\xe2\x94\x8f',
  'BOX DRAWINGS LIGHT DOWN AND LEFT'                      : '\xe2\x94\x90',
  'BOX DRAWINGS DOWN LIGHT AND LEFT HEAVY'                : '\xe2\x94\x91',
  'BOX DRAWINGS DOWN HEAVY AND LEFT LIGHT'                : '\xe2\x94\x92',
  'BOX DRAWINGS HEAVY DOWN AND LEFT'                      : '\xe2\x94\x93',
  'BOX DRAWINGS LIGHT UP AND RIGHT'                       : '\xe2\x94\x94',
  'BOX DRAWINGS UP LIGHT AND RIGHT HEAVY'                 : '\xe2\x94\x95',
  'BOX DRAWINGS UP HEAVY AND RIGHT LIGHT'                 : '\xe2\x94\x96',
  'BOX DRAWINGS HEAVY UP AND RIGHT'                       : '\xe2\x94\x97',
  'BOX DRAWINGS LIGHT UP AND LEFT'                        : '\xe2\x94\x98',
  'BOX DRAWINGS UP LIGHT AND LEFT HEAVY'                  : '\xe2\x94\x99',
  'BOX DRAWINGS UP HEAVY AND LEFT LIGHT'                  : '\xe2\x94\x9a',
  'BOX DRAWINGS HEAVY UP AND LEFT'                        : '\xe2\x94\x9b',
  'BOX DRAWINGS LIGHT VERTICAL AND RIGHT'                 : '\xe2\x94\x9c',
  'BOX DRAWINGS VERTICAL LIGHT AND RIGHT HEAVY'           : '\xe2\x94\x9d',
  'BOX DRAWINGS UP HEAVY AND RIGHT DOWN LIGHT'            : '\xe2\x94\x9e',
  'BOX DRAWINGS DOWN HEAVY AND RIGHT UP LIGHT'            : '\xe2\x94\x9f',
  'BOX DRAWINGS VERTICAL HEAVY AND RIGHT LIGHT'           : '\xe2\x94\xa0',
  'BOX DRAWINGS DOWN LIGHT AND RIGHT UP HEAVY'            : '\xe2\x94\xa1',
  'BOX DRAWINGS UP LIGHT AND RIGHT DOWN HEAVY'            : '\xe2\x94\xa2',
  'BOX DRAWINGS HEAVY VERTICAL AND RIGHT'                 : '\xe2\x94\xa3',
  'BOX DRAWINGS LIGHT VERTICAL AND LEFT'                  : '\xe2\x94\xa4',
  'BOX DRAWINGS VERTICAL LIGHT AND LEFT HEAVY'            : '\xe2\x94\xa5',
  'BOX DRAWINGS UP HEAVY AND LEFT DOWN LIGHT'             : '\xe2\x94\xa6',
  'BOX DRAWINGS DOWN HEAVY AND LEFT UP LIGHT'             : '\xe2\x94\xa7',
  'BOX DRAWINGS VERTICAL HEAVY AND LEFT LIGHT'            : '\xe2\x94\xa8',
  'BOX DRAWINGS DOWN LIGHT AND LEFT UP HEAVY'             : '\xe2\x94\xa9',
  'BOX DRAWINGS UP LIGHT AND LEFT DOWN HEAVY'             : '\xe2\x94\xaa',
  'BOX DRAWINGS HEAVY VERTICAL AND LEFT'                  : '\xe2\x94\xab',
  'BOX DRAWINGS LIGHT DOWN AND HORIZONTAL'                : '\xe2\x94\xac',
  'BOX DRAWINGS LEFT HEAVY AND RIGHT DOWN LIGHT'          : '\xe2\x94\xad',
  'BOX DRAWINGS RIGHT HEAVY AND LEFT DOWN LIGHT'          : '\xe2\x94\xae',
  'BOX DRAWINGS DOWN LIGHT AND HORIZONTAL HEAVY'          : '\xe2\x94\xaf',
  'BOX DRAWINGS DOWN HEAVY AND HORIZONTAL LIGHT'          : '\xe2\x94\xb0',
  'BOX DRAWINGS RIGHT LIGHT AND LEFT DOWN HEAVY'          : '\xe2\x94\xb1',
  'BOX DRAWINGS LEFT LIGHT AND RIGHT DOWN HEAVY'          : '\xe2\x94\xb2',
  'BOX DRAWINGS HEAVY DOWN AND HORIZONTAL'                : '\xe2\x94\xb3',
  'BOX DRAWINGS LIGHT UP AND HORIZONTAL'                  : '\xe2\x94\xb4',
  'BOX DRAWINGS LEFT HEAVY AND RIGHT UP LIGHT'            : '\xe2\x94\xb5',
  'BOX DRAWINGS RIGHT HEAVY AND LEFT UP LIGHT'            : '\xe2\x94\xb6',
  'BOX DRAWINGS UP LIGHT AND HORIZONTAL HEAVY'            : '\xe2\x94\xb7',
  'BOX DRAWINGS UP HEAVY AND HORIZONTAL LIGHT'            : '\xe2\x94\xb8',
  'BOX DRAWINGS RIGHT LIGHT AND LEFT UP HEAVY'            : '\xe2\x94\xb9',
  'BOX DRAWINGS LEFT LIGHT AND RIGHT UP HEAVY'            : '\xe2\x94\xba',
  'BOX DRAWINGS HEAVY UP AND HORIZONTAL'                  : '\xe2\x94\xbb',
  'BOX DRAWINGS LIGHT VERTICAL AND HORIZONTAL'            : '\xe2\x94\xbc',
  'BOX DRAWINGS LEFT HEAVY AND RIGHT VERTICAL LIGHT'      : '\xe2\x94\xbd',
  'BOX DRAWINGS RIGHT HEAVY AND LEFT VERTICAL LIGHT'      : '\xe2\x94\xbe',
  'BOX DRAWINGS VERTICAL LIGHT AND HORIZONTAL HEAVY'      : '\xe2\x94\xbf',
  'BOX DRAWINGS UP HEAVY AND DOWN HORIZONTAL LIGHT'       : '\xe2\x95\x80',
  'BOX DRAWINGS DOWN HEAVY AND UP HORIZONTAL LIGHT'       : '\xe2\x95\x81',
  'BOX DRAWINGS VERTICAL HEAVY AND HORIZONTAL LIGHT'      : '\xe2\x95\x82',
  'BOX DRAWINGS LEFT UP HEAVY AND RIGHT DOWN LIGHT'       : '\xe2\x95\x83',
  'BOX DRAWINGS RIGHT UP HEAVY AND LEFT DOWN LIGHT'       : '\xe2\x95\x84',
  'BOX DRAWINGS LEFT DOWN HEAVY AND RIGHT UP LIGHT'       : '\xe2\x95\x85',
  'BOX DRAWINGS RIGHT DOWN HEAVY AND LEFT UP LIGHT'       : '\xe2\x95\x86',
  'BOX DRAWINGS DOWN LIGHT AND UP HORIZONTAL HEAVY'       : '\xe2\x95\x87',
  'BOX DRAWINGS UP LIGHT AND DOWN HORIZONTAL HEAVY'       : '\xe2\x95\x88',
  'BOX DRAWINGS RIGHT LIGHT AND LEFT VERTICAL HEAVY'      : '\xe2\x95\x89',
  'BOX DRAWINGS LEFT LIGHT AND RIGHT VERTICAL HEAVY'      : '\xe2\x95\x8a',
  'BOX DRAWINGS HEAVY VERTICAL AND HORIZONTAL'            : '\xe2\x95\x8b',
  'BOX DRAWINGS LIGHT DOUBLE DASH HORIZONTAL'             : '\xe2\x95\x8c',
  'BOX DRAWINGS HEAVY DOUBLE DASH HORIZONTAL'             : '\xe2\x95\x8d',
  'BOX DRAWINGS LIGHT DOUBLE DASH VERTICAL'               : '\xe2\x95\x8e',
  'BOX DRAWINGS HEAVY DOUBLE DASH VERTICAL'               : '\xe2\x95\x8f',
  'BOX DRAWINGS DOUBLE HORIZONTAL'                        : '\xe2\x95\x90',
  'BOX DRAWINGS DOUBLE VERTICAL'                          : '\xe2\x95\x91',
  'BOX DRAWINGS DOWN SINGLE AND RIGHT DOUBLE'             : '\xe2\x95\x92',
  'BOX DRAWINGS DOWN DOUBLE AND RIGHT SINGLE'             : '\xe2\x95\x93',
  'BOX DRAWINGS DOUBLE DOWN AND RIGHT'                    : '\xe2\x95\x94',
  'BOX DRAWINGS DOWN SINGLE AND LEFT DOUBLE'              : '\xe2\x95\x95',
  'BOX DRAWINGS DOWN DOUBLE AND LEFT SINGLE'              : '\xe2\x95\x96',
  'BOX DRAWINGS DOUBLE DOWN AND LEFT'                     : '\xe2\x95\x97',
  'BOX DRAWINGS UP SINGLE AND RIGHT DOUBLE'               : '\xe2\x95\x98',
  'BOX DRAWINGS UP DOUBLE AND RIGHT SINGLE'               : '\xe2\x95\x99',
  'BOX DRAWINGS DOUBLE UP AND RIGHT'                      : '\xe2\x95\x9a',
  'BOX DRAWINGS UP SINGLE AND LEFT DOUBLE'                : '\xe2\x95\x9b',
  'BOX DRAWINGS UP DOUBLE AND LEFT SINGLE'                : '\xe2\x95\x9c',
  'BOX DRAWINGS DOUBLE UP AND LEFT'                       : '\xe2\x95\x9d',
  'BOX DRAWINGS VERTICAL SINGLE AND RIGHT DOUBLE'         : '\xe2\x95\x9e',
  'BOX DRAWINGS VERTICAL DOUBLE AND RIGHT SINGLE'         : '\xe2\x95\x9f',
  'BOX DRAWINGS DOUBLE VERTICAL AND RIGHT'                : '\xe2\x95\xa0',
  'BOX DRAWINGS VERTICAL SINGLE AND LEFT DOUBLE'          : '\xe2\x95\xa1',
  'BOX DRAWINGS VERTICAL DOUBLE AND LEFT SINGLE'          : '\xe2\x95\xa2',
  'BOX DRAWINGS DOUBLE VERTICAL AND LEFT'                 : '\xe2\x95\xa3',
  'BOX DRAWINGS DOWN SINGLE AND HORIZONTAL DOUBLE'        : '\xe2\x95\xa4',
  'BOX DRAWINGS DOWN DOUBLE AND HORIZONTAL SINGLE'        : '\xe2\x95\xa5',
  'BOX DRAWINGS DOUBLE DOWN AND HORIZONTAL'               : '\xe2\x95\xa6',
  'BOX DRAWINGS UP SINGLE AND HORIZONTAL DOUBLE'          : '\xe2\x95\xa7',
  'BOX DRAWINGS UP DOUBLE AND HORIZONTAL SINGLE'          : '\xe2\x95\xa8',
  'BOX DRAWINGS DOUBLE UP AND HORIZONTAL'                 : '\xe2\x95\xa9',
  'BOX DRAWINGS VERTICAL SINGLE AND HORIZONTAL DOUBLE'    : '\xe2\x95\xaa',
  'BOX DRAWINGS VERTICAL DOUBLE AND HORIZONTAL SINGLE'    : '\xe2\x95\xab',
  'BOX DRAWINGS DOUBLE VERTICAL AND HORIZONTAL'           : '\xe2\x95\xac',
  'BOX DRAWINGS LIGHT ARC DOWN AND RIGHT'                 : '\xe2\x95\xad',
  'BOX DRAWINGS LIGHT ARC DOWN AND LEFT'                  : '\xe2\x95\xae',
  'BOX DRAWINGS LIGHT ARC UP AND LEFT'                    : '\xe2\x95\xaf',
  'BOX DRAWINGS LIGHT ARC UP AND RIGHT'                   : '\xe2\x95\xb0',
  'BOX DRAWINGS LIGHT DIAGONAL UPPER RIGHT TO LOWER LEFT' : '\xe2\x95\xb1',
  'BOX DRAWINGS LIGHT DIAGONAL UPPER LEFT TO LOWER RIGHT' : '\xe2\x95\xb2',
  'BOX DRAWINGS LIGHT DIAGONAL CROSS'                     : '\xe2\x95\xb3',
  'BOX DRAWINGS LIGHT LEFT'                               : '\xe2\x95\xb4',
  'BOX DRAWINGS LIGHT UP'                                 : '\xe2\x95\xb5',
  'BOX DRAWINGS LIGHT RIGHT'                              : '\xe2\x95\xb6',
  'BOX DRAWINGS LIGHT DOWN'                               : '\xe2\x95\xb7',
  'BOX DRAWINGS HEAVY LEFT'                               : '\xe2\x95\xb8',
  'BOX DRAWINGS HEAVY UP'                                 : '\xe2\x95\xb9',
  'BOX DRAWINGS HEAVY RIGHT'                              : '\xe2\x95\xba',
  'BOX DRAWINGS HEAVY DOWN'                               : '\xe2\x95\xbb',
  'BOX DRAWINGS LIGHT LEFT AND HEAVY RIGHT'               : '\xe2\x95\xbc',
  'BOX DRAWINGS LIGHT UP AND HEAVY DOWN'                  : '\xe2\x95\xbd',
  'BOX DRAWINGS HEAVY LEFT AND LIGHT RIGHT'               : '\xe2\x95\xbe',
  'BOX DRAWINGS HEAVY UP AND LIGHT DOWN'                  : '\xe2\x95\xbf',
  'UPPER HALF BLOCK'                                      : '\xe2\x96\x80',
  'LOWER ONE EIGHTH BLOCK'                                : '\xe2\x96\x81',
  'LOWER ONE QUARTER BLOCK'                               : '\xe2\x96\x82',
  'LOWER THREE EIGHTHS BLOCK'                             : '\xe2\x96\x83',
  'LOWER HALF BLOCK'                                      : '\xe2\x96\x84',
  'LOWER FIVE EIGHTHS BLOCK'                              : '\xe2\x96\x85',
  'LOWER THREE QUARTERS BLOCK'                            : '\xe2\x96\x86',
  'LOWER SEVEN EIGHTHS BLOCK'                             : '\xe2\x96\x87',
  'FULL BLOCK'                                            : '\xe2\x96\x88',
  'LEFT SEVEN EIGHTHS BLOCK'                              : '\xe2\x96\x89',
  'LEFT THREE QUARTERS BLOCK'                             : '\xe2\x96\x8a',
  'LEFT FIVE EIGHTHS BLOCK'                               : '\xe2\x96\x8b',
  'LEFT HALF BLOCK'                                       : '\xe2\x96\x8c',
  'LEFT THREE EIGHTHS BLOCK'                              : '\xe2\x96\x8d',
  'LEFT ONE QUARTER BLOCK'                                : '\xe2\x96\x8e',
  'LEFT ONE EIGHTH BLOCK'                                 : '\xe2\x96\x8f',
  'RIGHT HALF BLOCK'                                      : '\xe2\x96\x90',
  'LIGHT SHADE'                                           : '\xe2\x96\x91',
  'MEDIUM SHADE'                                          : '\xe2\x96\x92',
  'DARK SHADE'                                            : '\xe2\x96\x93',
  'UPPER ONE EIGHTH BLOCK'                                : '\xe2\x96\x94',
  'RIGHT ONE EIGHTH BLOCK'                                : '\xe2\x96\x95',
  'QUADRANT LOWER LEFT'                                   : '\xe2\x96\x96',
  'QUADRANT LOWER RIGHT'                                  : '\xe2\x96\x97',
  'QUADRANT UPPER LEFT'                                   : '\xe2\x96\x98',
  'QUADRANT UPPER LEFT AND LOWER LEFT AND LOWER RIGHT'    : '\xe2\x96\x99',
  'QUADRANT UPPER LEFT AND LOWER RIGHT'                   : '\xe2\x96\x9a',
  'QUADRANT UPPER LEFT AND UPPER RIGHT AND LOWER LEFT'    : '\xe2\x96\x9b',
  'QUADRANT UPPER LEFT AND UPPER RIGHT AND LOWER RIGHT'   : '\xe2\x96\x9c',
  'QUADRANT UPPER RIGHT'                                  : '\xe2\x96\x9d',
  'QUADRANT UPPER RIGHT AND LOWER LEFT'                   : '\xe2\x96\x9e',
  'QUADRANT UPPER RIGHT AND LOWER LEFT AND LOWER RIGHT'   : '\xe2\x96\x9f',
  'BLACK SQUARE'                                          : '\xe2\x96\xa0',
  'WHITE SQUARE'                                          : '\xe2\x96\xa1',
  'WHITE SQUARE WITH ROUNDED CORNERS'                     : '\xe2\x96\xa2',
  'WHITE SQUARE CONTAINING BLACK SMALL SQUARE'            : '\xe2\x96\xa3',
  'SQUARE WITH HORIZONTAL FILL'                           : '\xe2\x96\xa4',
  'SQUARE WITH VERTICAL FILL'                             : '\xe2\x96\xa5',
  'SQUARE WITH ORTHOGONAL CROSSHATCH FILL'                : '\xe2\x96\xa6',
  'SQUARE WITH UPPER LEFT TO LOWER RIGHT FILL'            : '\xe2\x96\xa7',
  'SQUARE WITH UPPER RIGHT TO LOWER LEFT FILL'            : '\xe2\x96\xa8',
  'SQUARE WITH DIAGONAL CROSSHATCH FILL'                  : '\xe2\x96\xa9',
  'BLACK SMALL SQUARE'                                    : '\xe2\x96\xaa',
  'WHITE SMALL SQUARE'                                    : '\xe2\x96\xab',
  'BLACK RECTANGLE'                                       : '\xe2\x96\xac',
  'WHITE RECTANGLE'                                       : '\xe2\x96\xad',
  'BLACK VERTICAL RECTANGLE'                              : '\xe2\x96\xae',
  'WHITE VERTICAL RECTANGLE'                              : '\xe2\x96\xaf',
  'BLACK PARALLELOGRAM'                                   : '\xe2\x96\xb0',
  'WHITE PARALLELOGRAM'                                   : '\xe2\x96\xb1',
  'BLACK UP-POINTING TRIANGLE'                            : '\xe2\x96\xb2',
  'WHITE UP-POINTING TRIANGLE'                            : '\xe2\x96\xb3',
  'BLACK UP-POINTING SMALL TRIANGLE'                      : '\xe2\x96\xb4',
  'WHITE UP-POINTING SMALL TRIANGLE'                      : '\xe2\x96\xb5',
  'BLACK RIGHT-POINTING TRIANGLE'                         : '\xe2\x96\xb6',
  'WHITE RIGHT-POINTING TRIANGLE'                         : '\xe2\x96\xb7',
  'BLACK RIGHT-POINTING SMALL TRIANGLE'                   : '\xe2\x96\xb8',
  'WHITE RIGHT-POINTING SMALL TRIANGLE'                   : '\xe2\x96\xb9',
  'BLACK RIGHT-POINTING POINTER'                          : '\xe2\x96\xba',
  'WHITE RIGHT-POINTING POINTER'                          : '\xe2\x96\xbb',
  'BLACK DOWN-POINTING TRIANGLE'                          : '\xe2\x96\xbc',
  'WHITE DOWN-POINTING TRIANGLE'                          : '\xe2\x96\xbd',
  'BLACK DOWN-POINTING SMALL TRIANGLE'                    : '\xe2\x96\xbe',
  'WHITE DOWN-POINTING SMALL TRIANGLE'                    : '\xe2\x96\xbf',
  'BLACK LEFT-POINTING TRIANGLE'                          : '\xe2\x97\x80',
  'WHITE LEFT-POINTING TRIANGLE'                          : '\xe2\x97\x81',
  'BLACK LEFT-POINTING SMALL TRIANGLE'                    : '\xe2\x97\x82',
  'WHITE LEFT-POINTING SMALL TRIANGLE'                    : '\xe2\x97\x83',
  'BLACK LEFT-POINTING POINTER'                           : '\xe2\x97\x84',
  'WHITE LEFT-POINTING POINTER'                           : '\xe2\x97\x85',
  'BLACK DIAMOND'                                         : '\xe2\x97\x86',
  'WHITE DIAMOND'                                         : '\xe2\x97\x87',
  'WHITE DIAMOND CONTAINING BLACK SMALL DIAMOND'          : '\xe2\x97\x88',
  'FISHEYE'                                               : '\xe2\x97\x89',
  'LOZENGE'                                               : '\xe2\x97\x8a',
  'WHITE CIRCLE'                                          : '\xe2\x97\x8b',
  'DOTTED CIRCLE'                                         : '\xe2\x97\x8c',
  'CIRCLE WITH VERTICAL FILL'                             : '\xe2\x97\x8d',
  'BULLSEYE'                                              : '\xe2\x97\x8e',
  'BLACK CIRCLE'                                          : '\xe2\x97\x8f',
  'CIRCLE WITH LEFT HALF BLACK'                           : '\xe2\x97\x90',
  'CIRCLE WITH RIGHT HALF BLACK'                          : '\xe2\x97\x91',
  'CIRCLE WITH LOWER HALF BLACK'                          : '\xe2\x97\x92',
  'CIRCLE WITH UPPER HALF BLACK'                          : '\xe2\x97\x93',
  'CIRCLE WITH UPPER RIGHT QUADRANT BLACK'                : '\xe2\x97\x94',
  'CIRCLE WITH ALL BUT UPPER LEFT QUADRANT BLACK'         : '\xe2\x97\x95',
  'LEFT HALF BLACK CIRCLE'                                : '\xe2\x97\x96',
  'RIGHT HALF BLACK CIRCLE'                               : '\xe2\x97\x97',
  'INVERSE BULLET'                                        : '\xe2\x97\x98',
  'INVERSE WHITE CIRCLE'                                  : '\xe2\x97\x99',
  'UPPER HALF INVERSE WHITE CIRCLE'                       : '\xe2\x97\x9a',
  'LOWER HALF INVERSE WHITE CIRCLE'                       : '\xe2\x97\x9b',
  'UPPER LEFT QUADRANT CIRCULAR ARC'                      : '\xe2\x97\x9c',
  'UPPER RIGHT QUADRANT CIRCULAR ARC'                     : '\xe2\x97\x9d',
  'LOWER RIGHT QUADRANT CIRCULAR ARC'                     : '\xe2\x97\x9e',
  'LOWER LEFT QUADRANT CIRCULAR ARC'                      : '\xe2\x97\x9f',
  'UPPER HALF CIRCLE'                                     : '\xe2\x97\xa0',
  'LOWER HALF CIRCLE'                                     : '\xe2\x97\xa1',
  'BLACK LOWER RIGHT TRIANGLE'                            : '\xe2\x97\xa2',
  'BLACK LOWER LEFT TRIANGLE'                             : '\xe2\x97\xa3',
  'BLACK UPPER LEFT TRIANGLE'                             : '\xe2\x97\xa4',
  'BLACK UPPER RIGHT TRIANGLE'                            : '\xe2\x97\xa5',
  'WHITE BULLET'                                          : '\xe2\x97\xa6',
  'SQUARE WITH LEFT HALF BLACK'                           : '\xe2\x97\xa7',
  'SQUARE WITH RIGHT HALF BLACK'                          : '\xe2\x97\xa8',
  'SQUARE WITH UPPER LEFT DIAGONAL HALF BLACK'            : '\xe2\x97\xa9',
  'SQUARE WITH LOWER RIGHT DIAGONAL HALF BLACK'           : '\xe2\x97\xaa',
  'WHITE SQUARE WITH VERTICAL BISECTING LINE'             : '\xe2\x97\xab',
  'WHITE UP-POINTING TRIANGLE WITH DOT'                   : '\xe2\x97\xac',
  'UP-POINTING TRIANGLE WITH LEFT HALF BLACK'             : '\xe2\x97\xad',
  'UP-POINTING TRIANGLE WITH RIGHT HALF BLACK'            : '\xe2\x97\xae',
  'LARGE CIRCLE'                                          : '\xe2\x97\xaf',
  'WHITE SQUARE WITH UPPER LEFT QUADRANT'                 : '\xe2\x97\xb0',
  'WHITE SQUARE WITH LOWER LEFT QUADRANT'                 : '\xe2\x97\xb1',
  'WHITE SQUARE WITH LOWER RIGHT QUADRANT'                : '\xe2\x97\xb2',
  'WHITE SQUARE WITH UPPER RIGHT QUADRANT'                : '\xe2\x97\xb3',
  'WHITE CIRCLE WITH UPPER LEFT QUADRANT'                 : '\xe2\x97\xb4',
  'WHITE CIRCLE WITH LOWER LEFT QUADRANT'                 : '\xe2\x97\xb5',
  'WHITE CIRCLE WITH LOWER RIGHT QUADRANT'                : '\xe2\x97\xb6',
  'WHITE CIRCLE WITH UPPER RIGHT QUADRANT'                : '\xe2\x97\xb7',
  'UPPER LEFT TRIANGLE'                                   : '\xe2\x97\xb8',
  'UPPER RIGHT TRIANGLE'                                  : '\xe2\x97\xb9',
  'LOWER LEFT TRIANGLE'                                   : '\xe2\x97\xba',
  'WHITE MEDIUM SQUARE'                                   : '\xe2\x97\xbb',
  'BLACK MEDIUM SQUARE'                                   : '\xe2\x97\xbc',
  'WHITE MEDIUM SMALL SQUARE'                             : '\xe2\x97\xbd',
  'BLACK MEDIUM SMALL SQUARE'                             : '\xe2\x97\xbe',
  'LOWER RIGHT TRIANGLE'                                  : '\xe2\x97\xbf',
}

def symbol(sym):
  seq = utf_8_sequences[sym]
  return seq.decode('utf8')

class passwordList(urwid.WidgetWrap):
  def __init__(self, db):
    self.content = [ urwid.Button(x, self.select) for x in db ]
    lb = urwid.ListBox(self.content)
    urwid.WidgetWrap.__init__(self, lb)

  def keypress(self, size, key):
    if key == 'j' or key == 'k':
      self.content.append(urwid.Text(key))
      return
    return super(passwordList, self).keypress(size, key)

  def select(self, button):
    pass

class passwordForm(urwid.WidgetWrap):
  def __init__(self):
    urwid.WidgetWrap.__init__(self, urwid.SolidFill())
    self.lb = None
    self.editing = False

  def show(self, entry):
    self.entry = entry
    self.content = [urwid.Text('Name:'), urwid.Text(self.entry.name)]
    self._update()

  def edit(self, entry):
    self.entry = entry
    self.content = [urwid.Edit('Name: ', self.entry.name)] + \
      [ urwid.Edit(x+": ", entry[x]) for x in entry ] + \
      [ urwid.GridFlow(
          [urwid.Button('Save'), urwid.Button('Cancel') ],
          10, 3, 1, 'center')
      ]
    self.editing = True
    self._update()

  def keypress(self, size, key):
    if self.lb is None:
      return super(passwordForm, self).keypress(size, key)
    if key == 'tab': # FIXME: I'm certain there is a better way to do this
      focus_widget, position = self.lb.get_focus()
      self.lb.set_focus(position+1)
      return
    if key == 'shift tab':
      focus_widget, position = self.lb.get_focus()
      position = position-1
      if position >= 0:
        self.lb.set_focus(position)
      return
    return super(passwordForm, self).keypress(size, key)

  def _update(self):
    self.lb = urwid.ListBox(self.content)
    self._set_w(self.lb)

class koshUI(urwid.WidgetWrap):
  def __init__(self, db):
    self.db = weakref.proxy(db)
    self.pwList = passwordList(self.db)
    self.pwEntry = passwordForm()
    self.container = urwid.Columns( [
      ('weight', 0.75, self.pwList),
      ('fixed', 1, urwid.SolidFill(symbol('BOX DRAWINGS LIGHT VERTICAL'))),
      self.pwEntry
      ], dividechars=1 )
    self.frame = urwid.Frame(self.container,
        urwid.Divider(symbol('BOX DRAWINGS LIGHT HORIZONTAL')),
        urwid.Divider(symbol('BOX DRAWINGS LIGHT HORIZONTAL')))
    urwid.WidgetWrap.__init__(self, self.frame)

  def keypress(self, size, key):
    if key == 'n':
      import koshdb # FIXME: decouple this
      entry = koshdb.koshdb.passEntry(self.db._masterKeys[0])
      entry['Username'] = ''
      entry['Password'] = ''
      entry['URL'] = ''
      entry['Notes'] = '' # FIXME: Multi-line
      self.container.set_focus(self.pwEntry)
      self.pwEntry.edit(entry)
      return
    return super(koshUI, self).keypress(size, key)

  def showModal(self, parent=None):
    def exit_on_input(input):
      if input.lower() in ('escape'):
        raise urwid.ExitMainLoop()
    urwid.MainLoop(self, unhandled_input=exit_on_input).run()
