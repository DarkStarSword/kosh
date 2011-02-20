#!/usr/bin/env python2.6
# vi:sw=2:ts=2:expandtab

import sys
import csv

def promptOptions(prompt, options, default, help=None):
  """
  TTY user interraction routine

  Present user with some options and allow them to select one. A valid option
  must be selected. Help may optionally be provided for the options in the form
  of a parallel list with entries corresponding to those passed in options.
  """
  def showHelp():
    for (i,o) in enumerate(options):
      print '%s: %s'%(o, help[i])
  promptoptions = ','.join([ x.upper() if x==default else x.lower() for x in options ])
  if help:
    promptoptions += ',?'
  while True:
    ret = raw_input('%s (%s): '%(prompt, promptoptions)).lower()
    if ret == '': return default
    if ret in options: return ret
    if ret == '?' and help: showHelp()

def confirm(prompt):
  """
  TTY user interraction routine

  Simple ask for yes/no confirmation
  """
  return promptOptions(prompt, ('y','n'),'y') == 'y'

def prompt(prompt):
  """
  TTY user interraction routine

  Simple prompt for arbitrary input. Does not support a default value.
  """
  return raw_input(prompt+': ')

# FIXME: Use database constants and (possibly) list of all previously used values
knownFields = ['name','Username','Password','URL','Notes']
def recognisedField(field):
  return field.lower() in [ x.lower() for x in knownFields]

def translateCase(field):
  if not recognisedField(field): return field
  return knownFields[ [x.lower() for x in knownFields].index(field.lower()) ]

def askHeader(fp, cfp, field):
  """
  Prompt user for the name of a particular field header. Will present the user
  with a sample of data from records containing that field - the user can
  request additional examples. If no record has any data in the field this will
  return None without prompting. Confirms any non standard field names to avoid
  surprised users if they mispelled something.

  TTY only for now
  """
  loc = fp.tell()
  found = [False]
  try:
    def nextExample():
      """
      Get next example data or return None if no record is found containing
      data for this field.
      """
      while True:
        try:
          line = cfp.next()
          if line[field]:
            found[0] = True
            return line[field]
        except StopIteration:
          if not found[0]:
            print 'No data in field %i, disregarding'%field
            return None
          fp.seek(loc)
          continue

    example = nextExample()
    if not example: return None
    name = None
    while True:
      # TODO: Use readline to provide suggestions
      name = prompt('Field %i (example of data: %s)' % (field, example)).lower()
      if not name:
        ret = promptOptions('Disregard field %i?'%field, ('y','n','e'),'n',
            ('Yes','No','show next Example'))
        if ret == 'y': return None
        if ret == 'e': example = nextExample()
      elif recognisedField(name) or \
          confirm('Field name %s is not recognised, use anyway?'%name):
        return translateCase(name)
  finally:
    fp.seek(loc)

def askHeaders(fp, cfp, headers):
  """
  Prompts user for header names of each field, providing entry examples and
  confirmation for non standard names. Upon return the fp will have been seeked
  back to the location it was at when this function was called.

  If headers are provided they should be confirmed with the user, but this is
  not yet implemented - for now it will immediately return headers.

  TTY only for now
  """
  if headers:
    # TODO: Confirm headers. (TTY mode needs to implement prompt with default value - readline)
    # TODO: Strip blank headers and fields
    return map(translateCase, headers)

  if headers is None:
    loc = fp.tell()
    line = cfp.next()
    fp.seek(loc)
    headers = [None]*len(line)

  for field in range(len(headers)):
    headers[field] = askHeader(fp, cfp, field)

  return headers

def importCSV(filename, headers, db):
  fp = open(filename, 'rb')
  # TODO: If file not seekable, copy into cStringIO
  sample = fp.read(1024)
  fp.seek(0)
  dl = csv.Sniffer().sniff(sample)
  has_header = csv.Sniffer().has_header(sample)
  del sample
  cfp = csv.reader(fp, dl)
  if not headers and has_header:
    headers = cfp.next()
  # else - verify correct number of headers passed in

  headers = askHeaders(fp, cfp, headers)

  print 'Importing... '
  for line in cfp:
    entry = {}
    for (i, field) in enumerate(line):
      header=headers[i]
      if not header: continue
      if field:
        entry[header] = field
    #print 'Importing',entry
    if db.importEntry(entry):
      sys.stdout.write('.')
    else:
      sys.stdout.write('x')
  db.write()
  print ' done'
  fp.close()

passdb_default = '~/.kosh/koshdb' # FIXME: Also declared in kosh
def getParameters():
  # FIXME: Perhaps combine with main kosh getParameters...
  # or git approach is somewhat appealing, but for now:
  from optparse import OptionParser
  usage = 'usage: %prog CVSfile [passdb]'
  parser = OptionParser(usage=usage)
  parser.add_option('-d', '--database', dest='passdb', default=passdb_default)
  (options, args) = parser.parse_args()
  if len(args):
    options.CSVFilename = args.pop(0)
  else:
    parser.error('Did not pass CSV file')
  if len(args):
    options.headers = args
  else:
    options.headers = None
  return options

def main():
  import os,getpass,koshdb
  options = getParameters()
  try:
    db = koshdb.KoshDB(os.path.expanduser(options.passdb), getpass.getpass)
    importCSV(options.CSVFilename, options.headers, db)
  finally:
    db.__del__() # FIXME

if __name__ == '__main__':
  main()
