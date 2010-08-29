#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab

version = '0.1' #FIXME: use git describe if from git repository
passdb_default = '~/.koshdb'

from util.decorators import *
from util.err import urwidShowErr


def getParameters():
  import optparse
  usage = 'usage: %prog [passdb]'
  parser = optparse.OptionParser(usage=usage, version="%%prog %s" % version)
  # No non positional options just yet...
  (options, args) = parser.parse_args()

  # argparse from python2.7 would be nice, but I need to support older versions for now
  if len(args):
    options.passdb = args.pop(0)
  else:
    options.passdb = passdb_default

  if len(args):
    parser.error('Too many arguments')
  return options

@handleErr(urwidShowErr)
def main():
  import kosh
  options = getParameters()
  db = kosh.KoshDB(options.passdb) 

if __name__ == '__main__':
  main()
