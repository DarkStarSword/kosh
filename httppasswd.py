#!/usr/bin/env python
# vi:sw=2:ts=2:expandtab

# URLs will be a difficult case...
#  state -> logging in
#  goto URL
#  submit form | submit password
#  state -> logged in | failed
#  if logged in:
#   { goto URL || follow link }
#   state -> changing password
#   submit form
#   state -> password possibly changed | password changed | change failed
#   log out
# VERIFY:
#  state -> verifying change
#  goto URL
#  submit form | submit password
#  state -> change succeeded | verification stage failed
#
# Actions for:
#  GOTO URL
#  Follow link on page (regexp match?)
#  Fill in form
#  Submit form

import urllib2
import urlparse
import cookielib
import HTMLParser

import socket
import ssl
import version

USER_AGENT="kosh %s"%version.__version__
TIMEOUT=10 # FIXME: Configurable
TRIES=5
DEBUG=True

class _CancelAction(Exception): pass
class ReplayFailure(Exception): pass

class urlvcr_action(object):
  # Defaults unless action defines otherwise:
  changes_state = True
  use_referer = True

  def valid(self, state):
    raise NotImplementedError()
  def help(self, state):
    return "Missing help text"
  def ask_params(self, ui, state):
    return None
  def apply(self, ui, state, params):
    raise NotImplementedError()

class action_debug(urlvcr_action):
  counter = 0
  def valid(self,state): return DEBUG
  def apply(self, ui, state, params):
    fp = open('index.html')
    if params:
      state.url = params
    else:
      state.url = 'DEBUG %i'%self.counter
      self.counter += 1
    state.body = fp.read()
    fp.close()

class action_goto(urlvcr_action):
  use_referer = False
  def valid(self, state):
    return True
  def help(self, state):
    return "Goto URL"
  def ask_params(self, ui, state):
    while True:
      url = raw_input('Enter URL: ')
      if url == '':
        raise _CancelAction()
      if url.find('://') != -1:
        break
      if ui.confirm("No protocol specified - assume http?", True):
        url = 'http://'+url
        break
    return url
  def apply(self, ui, state, url):
    state.request(ui, url)

class action_quit(urlvcr_action):
  changes_state = False
  def valid(self, state):
    return True
  def help(self, state):
    return "Quit"
  def ask_params(self, ui, state):
    raise StopIteration('Quit')

class action_undo(urlvcr_action):
  changes_state = False # Technically we do, but this prevents a new state being pushed
  def valid(self, state):
    return state.state is not None
  def help(self, state):
    return "Undo last action (Deletes action entirely. Caution advised)"
  def apply(self, ui, state, params):
    state.pop()

class action_back(urlvcr_action):
  def valid(self, state):
    node = self._walk(state.state, 1)
    return node is not None
  def help(self, state):
    return "Go back in history (recording this as an action)"
  def apply(self, ui, state, params):
    # new state has already been pushed, so need parent of parent:
    node = self._walk(state.parent, 1)
    if node.url.startswith('DEBUG'):
      return actions['#'].apply(ui, state, node.url+'b')
    state.request(ui, node.url)
  def _walk(self, node, num):
    while node and (num or node.action[0] == 'b'):
      if node.action[0] == 'b':
        params = node.action[1]
        num += params if params else 1
      else:
        num -= 1
      node = node.parent
    return node

def select_element(ui, prompt, original_elements):
  unfiltered_elements = [ x for x in original_elements if x.selectable() ]
  if not len(unfiltered_elements):
    raise _CancelAction('No selectable elements found of matching type')
  elements = unfiltered_elements
  while True:
    if not len(elements):
      elements = unfiltered_elements
    if len(elements) == 1:
      return elements[0]
    ui._print('\n'.join(map(str,elements)))
    filter = raw_input(prompt)
    if not filter:
      raise _CancelAction('User aborted')
    elements = [ x for x in elements if hasattr(x, 'matches') and x.matches(filter) ]

def find_element(original_elements, filters):
  elements = [ x for x in original_elements if x.selectable() ]
  if not len(elements):
    raise ReplayFailure('No selectable elements found of matching type')
  for filter in filters:
    elements = [ x for x in elements if hasattr(x, 'matches') and x.matches(filter) ]
  if not len(elements):
    raise ReplayFailure('All selectable elements of matching type were filtered')
  if len(elements) > 1:
    raise ReplayFailure('Multiple elements were matched by filters')
  return elements[0]

class action_link(urlvcr_action, HTMLParser.HTMLParser):
  def valid(self, state):
    return state.state is not None and state.body is not None
  def help(self, state):
    return "Follow link on current page"
  def ask_params(self, ui, state):
    self.update(ui, state)
    while True:
      link = select_element(ui, "Enter part of the link to follow: ", self.links)
      try:
        url = link['href']
      except KeyError:
        ui._cprint("red", 'No HREF attribute in link')
      else:
        url = urlparse.urljoin(state.url, url)
        if ui.confirm('Follow link "%s" to %s'%(ui._ctext('yellow', link.data), ui._ctext('blue', url)), True):
          return link.data
        raise _CancelAction('User aborted')
  def apply(self, ui, state, link):
    self.update(ui, state)
    link = find_element(self.links, [link])
    url = urlparse.urljoin(state.url, link['href'])
    state.request(ui, url)

  class Link(dict):
    def __init__(self, d, ui):
      self.data = ''
      self._ui = ui
      dict.__init__(self,d)
    def selectable(self):
      if not 'href' in self:
        self._ui._cprint('dark red', 'filtering out link with no URL')
        return False
      return True
    def matches(self, match):
      return match.lower() in self.data.lower()
    def __str__(self):
      return "%50s -> %s"%(
        '"%s"'%self._ui._ctext('yellow', self.data) if self.data else self._ui._ctext('reset', '<NO TEXT LINK>'),
        self._ui._ctext('blue', self['href']) if 'href' in self else '<NO URL>'
      )

  def update(self, ui, state):
    self.reset()
    self._ui = ui
    food = state.body
    while True:
      try:
        self.feed(food)
      except HTMLParser.HTMLParseError, e:
        self._ui._cprint('red', 'HTMLParseError: %s'%e)
        lineno = e.lineno
        offset = e.offset
        food = '\n'.join(food.split('\n')[lineno-1:])[offset:]
        HTMLParser.HTMLParser.reset(self) # Reset count
        continue
      break
  def reset(self):
    self.links = []
    self.dom = []
    HTMLParser.HTMLParser.reset(self)
  def handle_starttag(self, tag, attrs):
    if tag == 'a':
      self.dom.append(self.Link(attrs, self._ui))
      #self._ui._cprint('blue', '%i: <a href="%%s">, attrs:%s'%(self.in_links,repr(dict(attrs))))
    # FIXME: Catch images (alttext, url) or other objects that could identify a link
  def handle_endtag(self, tag):
    if tag == 'a':
      if not len(self.dom):
        #self._ui._cprint('yellow', '</a INVALID>')
        return
      link = self.dom.pop()
      link.data = ' '.join(link.data.split()) #Normalise whitespace
      self.links.append(link)
      #self._ui._cprint('blue', '%i: </a>'%self.in_links)
  def handle_data(self, data):
    if len(self.dom):
      #self._ui._cprint('dark blue', data)
      self.dom[-1].data += data

class action_form(urlvcr_action, HTMLParser.HTMLParser):
  field_actions = { # Fixme: Make these their own context aware functions in the same style the urlvcr actions are:
      'x': 'Leave unchanged',
      's': 'Set a specific value', # ... then add a separate 'checked' action for checkboxes
      'u': 'Fill in with username',
      'o': 'Fill in with old password',
      'n': 'Fill in with new password',
  }
  def valid(self, state):
    return state.state is not None and state.body is not None
  def help(self, state):
    return "Fill in and submit form on current page"
  def ask_params(self, ui, state):
    self.update(ui, state)
    form = select_element(ui, "Enter part of the %s name or action to fill in: "%ui._ctext('yellow', 'form'), self.forms)
    form.editing = True
    while True:
      ui._print(str(form))
      idx = raw_input("Enter %s index to edit, 's' to submit, 'a' to add an additional value: "%ui._ctext('dark green', 'field'))
      if not idx:
        if ui.confirm('Really discard form?', False):
          raise _CancelAction('User aborted')
        continue
      if idx.lower() == 's':
        if ui.confirm('Really submit form to %s *without* using submit button?'%(
          ui._ctext('blue', form['action'])), False):
          return form.submit(None)
      if idx.lower() == 'a':
        name = raw_input('New field name: ')
        if not name: continue
        # FIXME: Verify field not already in form
        field = action_form.Form.Field({'name': name, 'value': ''}, ui)
        field.additional = True
        form.fields.append(field)
        idx = str(len(form.fields) - 1)
      if not idx.isdigit():
        continue
      idx = int(idx)
      try:
        field = form.fields[idx]
      except IndexError:
        continue
      if type(field) != action_form.Form.Field:
        continue
      if field.gettype() == 'submit':
        v = field.getvalue()
        if not ui.confirm('Submit form via %s button to %s?'%(
          ui._ctext('yellow', v) if v else '<UNNAMED>',
          ui._ctext('blue', form['action'])), True
        ): continue
        return form.submit(field)

      # FIXME: Most of this stuff should be moved into appropriate classes:
      action = ui.read_nonbuffered('Enter action for this field:\n'+
          '\n'.join(['  %s: %s'%(k,v) for (k,v) in action_form.field_actions.items()])+
          '\n> ')
      if action not in action_form.field_actions:
        continue
      if field.gettype() == 'radio':
        if action in ['s', 'x']:
          name = field.getname()
          for f in form.fields:
            if type(f) == action_form.Form.Field and f.getname() == name:
              f.action = action
              f.checked = False
          field.checked = action == 's'
      else:
        field.action = action
        if action == 's':
          val = raw_input('Enter new value: ')
          field.value = val
        elif action == 'u':
          if state.username is None or ui.confirm('Set new username?', False):
            state.username = raw_input('Enter Username: ')
          field.value = state.username
        elif action in ['o','n']:
          field.value = '********'
          import getpass # FIXME: UI
          if action == 'o' and (state.oldpass is None or ui.confirm('Reset OLD password?', False)):
            state.oldpass = getpass.getpass('Enter OLD Password: ')
          elif action == 'n' and (state.newpass is None or ui.confirm('Reset NEW password?', False)):
            state.newpass = getpass.getpass('Enter NEW Password: ')
        elif action == 'x' and field.additional:
          del form.fields[idx]

  def apply(self, ui, state, (form_name, form_action, form_method, form_script)):
    self.update(ui, state)
    # form_action may not match if the submission URL changes, for now just match on name:
    form = find_element(self.forms, [form_name] if form_name is not None else [])
    #form = find_element(self.forms, [x for x in [form_name, form_action] if x is not None])
    # XXX: Similar logic to submitting above, can probably refactor this:
    data = {}
    fields = []
    for f in form.fields:
      if type(f) != action_form.Form.Field:
        continue
      field_name = f.getname()
      fields.append(field_name)
      t = f.gettype()
      if t == 'submit':
        pass # Only pressed submit button sent
      elif t == 'radio' and not f.getchecked():
        pass # Don't submit unchecked radio buttons
      else: # Otherwise, add it:
        data[field_name] = f.getvalue()
    # Now, fill in details saved from form:
    for f in form_script:
      (action, params) = form_script[f]
      if action.startswith('a'):
        # Additional item, not in original form
        action = action.lstrip('a')
      else:
        if f not in fields:
          raise ReplayFailure('Filling in form failed: Saved field %s not found in current form',f)
      if action == 's':
        data[f] = params
      elif action == 'u':
        if state.username is None:
          state.username = raw_input('Enter Username: ')
        data[f] = state.username
      elif action == 'o':
        if state.oldpass is None:
          import getpass # FIXME: UI
          state.oldpass = getpass.getpass('Enter OLD Password: ')
        data[f] = state.oldpass
      elif action == 'n':
        if state.newpass is None:
          import getpass # FIXME: UI
          state.newpass = getpass.getpass('Enter NEW Password: ')
        data[f] = state.newpass
      else:
        raise ReplayFailure('Invalid action while filling in form: %s'%action)
    url = urlparse.urljoin(state.url, form_action)
    if form_method.upper() == 'POST':
      state.request(ui, url, post=data)
    else:
      state.request(ui, url, get=data)

  class Form(dict):
    class Field(dict):
      def __init__(self, d, ui):
        self.action = 'x'
        self.additional = False
        self.checked = False
        self._ui = ui
        dict.__init__(self,d)
        self.value = self['value'] if 'value' in self else ''
      def __str__(self):
        if self.action == 'x':
          val = '%s"%s"'%(
            self._ui._ctext('bright cyan', '* ') if self.getchecked() else '',
            self._ui._ctext('magenta', self.getvalue())
          )
        else:
          val = '%s: %s"%s"'%(
            self._ui._ctext('red', self.action),
            self._ui._ctext('bright cyan', '* ') if self.getchecked() else '',
            self._ui._ctext('yellow', self.getvalue())
          )
        type = self.gettype()
        return '%30s %-34s: %s'%(
            '"%s"'%self._ui._ctext('dark yellow', self['name']) if 'name' in self else self._ui._ctext('reset','<UNNAMED>'),
            '(%s)'%self._ui._ctext('dark green', type) if type else self._ui._ctext('reset','<UNSPECIFIED>'),
            val,
        )
      def getname(self):
        return self['name'] if 'name' in self else None
      def getvalue(self):
        if self.action == 'x':
          return self['value'] if 'value' in self else ''
        else:
          return self.value
      def getchecked(self):
        if self.gettype() != 'radio': return None
        if self.action == 'x':
          return 'checked' in self and self['checked']
        else:
          return self.checked
      def gettype(self):
        return self['type'].lower() if 'type' in self else None

    def __init__(self, d, ui):
      self.fields = []
      self.editing = False
      self._ui = ui
      dict.__init__(self,d)
    def selectable(self):
      if not 'action' in self:
        self._ui._cprint('red', 'filtering out form with missing action')
        return False
      return True
    def matches(self, match):
      return 'name' in self and match.lower() in self['name'].lower() or 'action' in self and match.lower() in self['action'].lower()
    def __str__(self):
      return 'Form %s (action: %s)\n%s' % (
        '"%s"'%self._ui._ctext('yellow', self['name']) if 'name' in self else '<UNNAMED>',
        '"%s"'%self._ui._ctext('blue', self['action']) if 'action' in self else '<NO_ACTION>',
        '\n'.join([
          '%s\t%s'%(
            '%i:'%idx if self.editing else '',
            str(field)
          ) if type(field) == action_form.Form.Field else
          '\t%46s'%('"%s"'%self._ui._ctext('dark blue', field))
        for (idx, field) in enumerate(self.fields) ])
      )
    def getname(self):
      return self['name'] if 'name' in self else None
    def getaction(self):
      return self['action'] if 'action' in self else None
    def getmethod(self):
      return self['method'] if 'method' in self else 'GET'
    # def __hash__(self): Considder hashing the names of the form and fields and only the names to make this identifyable even on pages where (say) the form action is dynamic
    def submit(self, submit_button=None):
      ret = {}
      for f in self.fields:
        if type(f) != action_form.Form.Field:
          continue
        t = f.gettype()
        if t == 'submit':
          pass # Only pressed submit button sent
        elif t == 'radio' and not f.getchecked():
          pass # Don't submit unchecked radio buttons
        else: # Otherwise, add it:
          action = f.action
          additional = 'a' if f.additional else ''
          if action == 's':
            ret[f.getname()] = (additional+action, f.getvalue())
          elif action in ['u', 'o', 'n']:
            ret[f.getname()] = (additional+action, None)
      if submit_button is not None:
        ret[submit_button.getname()] = ('s', submit_button.getvalue()) # submit button
      return (self.getname(), self.getaction(), self.getmethod(), ret)

  def update(self, ui, state):
    self.reset()
    self._ui = ui
    food = state.body
    while True:
      try:
        self.feed(food)
      except HTMLParser.HTMLParseError, e:
        self._ui._cprint('red', 'HTMLParseError: %s'%e)
        lineno = e.lineno
        offset = e.offset
        food = '\n'.join(food.split('\n')[lineno-1:])[offset:]
        HTMLParser.HTMLParser.reset(self) # Reset count
        continue
      break
  def reset(self):
    self.forms = []
    self.dom = []
    HTMLParser.HTMLParser.reset(self)
  def handle_starttag(self, tag, attrs):
    colour = 'dark yellow'
    if tag == 'form':
      self.dom.append(self.Form(attrs, self._ui))
    elif tag == 'input':
      if not len(self.dom):
        self._ui._cprint('red', '<input INVALID>')
        return
      self.dom[-1].fields.append(action_form.Form.Field(attrs, self._ui))
    else:
      return
      colour = 'grey'
    #self._ui._cprint(colour, '%i: <%s>, attrs:%s'%(len(self.dom),tag,repr(dict(attrs))))
  def handle_endtag(self, tag):
    colour = 'dark yellow'
    if tag == 'form':
      if not len(self.dom):
        self._ui._cprint('red', '</form INVALID>')
        return
      form = self.dom.pop()
      self.forms.append(form)
    else:
      return
      #colour = 'grey'
    #self._ui._cprint(colour, '%i: </%s>'%(len(self.dom), tag))
  def handle_data(self, data):
    if len(self.dom):
      data = ' '.join(data.split()) # Normalise whitespace
      if data:
        #self._ui._cprint('dark blue', data)
        try:
          if type(self.dom[-1].fields[-1]) == str:
            self.dom[-1].fields[-1] += ' '+data
            return
        except IndexError: pass
        self.dom[-1].fields.append(data)

# TODO: Inherit from a common class when just setting a parameter in the state:
class action_agent(urlvcr_action):
  def valid(self, state):
    return True
  def help(self, state):
    return "Override User Agent string"
  def ask_params(self, ui, state):
    agent = raw_input("New User Agent: ")
    if not agent:
      raise _CancelAction('User aborted')
    return agent
  def apply(self, ui, state, agent):
    state.user_agent = agent

class action_referer(urlvcr_action):
  def valid(self, state):
    return True
  def help(self, state):
    return "Override Referer URL"
  def ask_params(self, ui, state):
    referer = raw_input("New Referer URL: ")
    return referer if referer else None
  def apply(self, ui, state, referer):
    state.override_referer = referer

class action_view(urlvcr_action):
  changes_state = False
  def valid(self, state):
    return state.state is not None and state.body is not None
  def help(self, state):
    return "View source + headers"
  def apply(self, ui, state, params):
    ui._cprint('bright cyan', str(state.info))
    ui._print(state.body)

class action_meta(urlvcr_action, HTMLParser.HTMLParser):
  def valid(self, state, ui=None):
    if state.state is None or state.state.body is None:
      return False
    self.update(ui, state)
    return self.refresh is not None
  def help(self, state):
    return "Follow meta refresh tag if present (usually involked automatically)"
  def apply(self, ui, state, params):
    self.update(ui, state)
    if self.refresh is None:
      raise ReplayFailure('No meta refresh tag, or unable to parse')
    url = urlparse.urljoin(state.url, self.refresh)
    state.request(ui, url)

  def update(self, ui, state):
    self.reset()
    self._ui = ui
    food = state.body
    while True:
      try:
        self.feed(food)
      except HTMLParser.HTMLParseError, e:
        if self._ui:
          self._ui._cprint('red', 'HTMLParseError: %s'%e)
        else:
          print 'HTMLParseError: %s'%e
        lineno = e.lineno
        offset = e.offset
        food = '\n'.join(food.split('\n')[lineno-1:])[offset:]
        HTMLParser.HTMLParser.reset(self) # Reset count
        continue
      break
  def reset(self):
    self.refresh = None
    HTMLParser.HTMLParser.reset(self)
  def handle_starttag(self, tag, attrs):
    if tag == 'meta':
      attrs = dict(attrs)
      if 'http-equiv' in attrs and 'content' in attrs and attrs['http-equiv'].lower() == 'refresh':
        # FIXME: Python 2.5 will not unescape attrs for us, so this won't work
        try:
          #self.refresh = [ x for x in attrs['content'].split() if x.startswith('url=') ][0][4:].strip("'")
          self.refresh = attrs['content'].lower().partition('url=')[2].strip("'")
        except IndexError:
          self._ui._cprint('red', 'Error parsing meta refresh tag') # FIXME: if called from display_valid_actions, ui==None

class action_auth(urlvcr_action):
  def valid(self, state):
    return state.state is not None and state.state.info is not None \
        and 'www-authenticate' in state.state.info
  def help(self, state):
    return "Authenticate with basic or digest authentication in the current realm"
  def ask_params(self, ui, state):
    header = state.info['www-authenticate']
    if not header.startswith('Basic realm="'):
      ui._cprint('red', "Don't know how to handle authentication type %s"%header)
      raise _CancelAction
    try:
      realm = header.split('"')[1]
    except IndexError:
      ui._cprint('red', "Error parsing www-authenticate header")
      raise _CancelAction
    import getpass # FIXME: UI
    if ui.confirm('Override username?', False):
      username = ('s', raw_input('Username: '))
    else:
      username = ('u', None)
      if state.username is None:
        state.username = raw_input('Enter Username: ')
    if ui.confirm('Override password?', False):
      password = ('s', getpass.getpass('Password: '))
    elif ui.confirm('Authenticate with old password?', True):
      password = ('o', None)
      if state.oldpass is None:
        state.oldpass = getpass.getpass('Enter OLD Password: ')
    else:
      password = ('n', None)
      if state.newpass is None:
        state.newpass = getpass.getpass('Enter NEW Password: ')
    url = state.url # What is the URL supposed to be?
    # FIXME: This will fail if authentication is on root directory:
    url = url.rsplit('/',1)[0] # Directory?
    return ('basic', realm, url, username, password)

  def apply(self, ui, state,
            (auth_type, realm, url,
             (username_type, username_override),
             (password_type, password_override))):
    if auth_type != 'basic':
      raise ReplayFailure('only basic authentication supported for now')
    pwmgr = urllib2.HTTPPasswordMgr()
    if username_type == 'u':
      username = state.username
    elif username_type == 's':
      username = username_override
    else:
      raise ReplayFailure('Invalid username type')

    if password_type == 'o':
      password = state.oldpass
    elif password_type == 'n':
      password = state.newpass
    elif password_type == 's':
      password = password_override
    else:
      raise ReplayFailure('Invalid password type')
    pwmgr.add_password(realm, url, username, password)
    authmgr = urllib2.HTTPBasicAuthHandler(pwmgr)
    # FIXME: This won't be undone properly, and will mess up if we auth multiple times:
    state.handlers.append(authmgr)
    state.opener = urllib2.build_opener(*state.handlers)
    ui._cprint('yellow', "Authentication credentials set - you probably want to refresh now ('r').")

class action_refresh(urlvcr_action):
  def valid(self, state):
    return state.state is not None and state.url
  def help(self, state):
    return "Refresh the current page"
  def apply(self, ui, state, params):
    state.request(ui, state.url)

class action_frame(urlvcr_action, HTMLParser.HTMLParser):
  def valid(self, state):
    return state.state is not None and state.body is not None
  def help(self, state):
    return "Enter frame on current page"
  def ask_params(self, ui, state):
    self.update(ui, state)
    while True:
      frame = select_element(ui, "Enter part of the frame name or URL to enter: ", self.frames)
      name = frame['name']
      src = frame['src']
      url = urlparse.urljoin(state.url, src)
      if ui.confirm('Enter frame "%s" to %s'%(ui._ctext('yellow', name), ui._ctext('blue', url)), True):
        return (name, src)
      raise _CancelAction('User aborted')
  def apply(self, ui, state, (name, src)):
    self.update(ui, state)
    frame = find_element(self.frames, [name, src])
    url = urlparse.urljoin(state.url, frame['src'])
    state.request(ui, url)

  class Frame(dict):
    def __init__(self, d, ui):
      self._ui = ui
      dict.__init__(self,d)
    def selectable(self):
      if 'src' not in self:
        self._ui._cprint('dark red', 'filtering out frame with no SRC')
        return False
      return True
    def matches(self, match):
      return 'name' in self and match.lower() in self['name'].lower() or 'src' in self and match.lower() in self['src'].lower()
    def __str__(self):
      return '%30s : %s' % (
        '"%s"'%self._ui._ctext('yellow', self['name']) if 'name' in self else self._ui.ctext('reset', '<UNNAMED>'),
        '"%s"'%self._ui._ctext('blue', self['src']) if 'src' in self else '<NO_SRC>',
      )

  def update(self, ui, state):
    self.reset()
    self._ui = ui
    food = state.body
    while True:
      try:
        self.feed(food)
      except HTMLParser.HTMLParseError, e:
        self._ui._cprint('red', 'HTMLParseError: %s'%e)
        lineno = e.lineno
        offset = e.offset
        food = '\n'.join(food.split('\n')[lineno-1:])[offset:]
        HTMLParser.HTMLParser.reset(self) # Reset count
        continue
      break
  def reset(self):
    self.refresh = None
    self.frames = []
    HTMLParser.HTMLParser.reset(self)
  def handle_starttag(self, tag, attrs):
    if tag == 'frame':
      self.frames.append(action_frame.Frame(attrs, self._ui))

class action_save(urlvcr_action):
  changes_state = False
  def valid(self, state):
    return state.state is not None and state.body is not None
  def help(self, state):
    return "Save the current page to a file"
  def ask_params(self, ui, state):
    filename = raw_input('Filename: ')
    if not filename:
      raise _CancelAction('User aborted')
    return filename
  def apply(self, ui, state, filename):
    fp=None
    try:
      fp = open(filename,'wb')
      fp.write(state.body)
    except Exception,e:
      self._ui._cprint('red', 'Exception while saving file: %s'%e)
    finally:
      if fp is not None:
        fp.close()

class urlvcr_actions(dict):
  def display_valid_actions(self, ui, state):
    for action in sorted(self):
      if self[action].valid(state):
        ui._print("  %s: %s"%(action, self[action].help(state)))

  def ask_next_action(self, ui, state):
    import sys
    ui._cprint('green', str(state))
    action=''
    ui._print("-------------")
    while True:
      ui._print("Enter action:")
      actions.display_valid_actions(ui, state)
      action = ui.read_nonbuffered("> ").lower()
      if action not in self or not self[action].valid(state):
        ui._print("%s: Invalid action from current state\n"%repr(action))
        continue
      try:
        params = self[action].ask_params(ui, state)
      except _CancelAction:
        continue
      return (action, params)

# ABI WARNING: Do not reassign letters without bumping db version & implementing conversion - these are saved in the scripts
actions = urlvcr_actions({
  '#': action_debug(),
  'g': action_goto(),
  'q': action_quit(), # Doesn't change state, OK to alter
  'u': action_undo(), # Doesn't change state, OK to alter
  'b': action_back(),
  'l': action_link(),
  'f': action_form(),
  't': action_agent(),
  'R': action_referer(),
  'v': action_view(), # Doesn't change state, OK to alter
  'a': action_auth(),
  'r': action_refresh(),
  'm': action_frame(),
  'w': action_save(), # Doesn't change state, OK to alter
  #'m': action_meta(), # Usually involked automatically
})

def get_actions_ask(ui, state):
  while True:
    yield actions.ask_next_action(ui, state)

def get_actions_from_script(ui, state, script):
  for action in script:
    ui._cprint('white', 'Replaying action %s...'%action)
    yield action
    ui._cprint('green', 'Current State:\n%s'%str(state))

def apply_action(ui, state, action):
  a = actions[action[0]]
  if a.changes_state:
    state.push(action)
  try:
    a.apply(ui, state, action[1])
  except urllib2.URLError, socket.timeout:
    assert(a.changes_state)
    ui._cprint('dark red', 'Unhandled URLError, undoing last action')
    state.pop()

class urlvcr(object):
  """
  Linked list of states, including URL, cookies, etc. Used to produce a script
  for later replay.
  """
  state = None
  def __init__(self, username=None, oldpass=None, newpass=None):
    self.username = username
    self.oldpass = oldpass
    self.newpass = newpass

  class urlstate(object):
    def __init__(self, parent, action):
      self.parent = parent
      self.action = action
      if self.parent:
        self.cookies = self.parent.cookies # XXX Likely need to copy this and create new opener, maybe just copy when doing request
        self.handlers = self.parent.handlers
        self.opener = self.parent.opener # XXX: May need to copy this if we change it's state
        self.url = self.parent.url
        self.info = self.parent.info
        self.body = self.parent.body
        self.override_referer = self.parent.override_referer
        self.user_agent = self.parent.user_agent
      else:
        self.cookies = cookielib.CookieJar()
        self.handlers = [urllib2.HTTPCookieProcessor(self.cookies)]
        self.opener = urllib2.build_opener(*self.handlers)
        self.url = None
        self.info = None
        self.body = None
        self.override_referer = None
        self.user_agent = USER_AGENT

    def list(self):
      ret = []
      if self.parent is not None:
        ret = self.parent.list()
      return ret + [{'action': self.action, 'url': self.url}] #, 'info': self.info, 'body': self.body}]

  def push(self, action):
    self.state = urlvcr.urlstate(self.state, action)

  def pop(self):
    assert(self.state is not None)
    self.state = self.state.parent

  def request(self, ui, url, post=None, get=''):
    # FIXME: show progress:
    import urllib
    if post:
      post = urllib.urlencode(post)
    if get:
      get = '?'+urllib.urlencode(get)

    request = urllib2.Request(url+get, post)

    referer = None
    if self.state.override_referer:
      referer = self.state.override_referer
    elif actions[self.state.action[0]].use_referer and self.state.parent is not None:
        referer = self.state.parent.url
    if referer is not None:
      request.add_header('Referer', referer)

    if self.state.user_agent:
      request.add_header('User-agent', self.state.user_agent)

    tries = TRIES
    while (tries):
      tries -= 1
      ui._cprint('bright cyan', '[%i/%i]: Navigating to: %s%s'%(TRIES-tries,TRIES,url,get))
      if referer is not None:
        ui._cprint('cyan', 'Referer: %s'%referer)
      if self.state.user_agent:
        ui._cprint('cyan', 'User-agent: %s'%self.state.user_agent)

      try:
        try:
          response = self.state.opener.open(request, timeout=TIMEOUT)
        except TypeError:
          # Python 2.5 does not support a timeout throught urllib2:
          socket.setdefaulttimeout(TIMEOUT)
          response = self.state.opener.open(request)
      except urllib2.HTTPError, e:
        if e.code == 401:
          ui._cprint('red', 'HTTP status code: %s: %s'%(e.code, e.msg))
          response = e
        else:
          ui._cprint('red', 'HTTP status code: %s: %s'%(e.code, e.msg))
          raise
      except (urllib2.URLError, socket.timeout), e:
        if hasattr(e, 'reason'):
          ui._cprint('red', 'Failed to reach server: %s'%e.reason)
        else:
          ui._cprint('red', 'Failed to reach server: timeout')
        if tries:
          ui._cprint('dark red', 'Retrying...')
          continue
        raise
      break
    try:
      self.state.url = response.geturl()
    except AttributeError:
      ui._cprint('red', 'Response did not contain a URL, assuming we went to the requested URL...')
      self.state.url = url
    self.state.info = response.info()
    self.state.body = ''
    tries = TRIES
    while (tries):
      tries -= 1
      try:
        self.state.body += response.read()
      except (socket.timeout, urllib2.URLError, ssl.SSLError), e:
        ui._cprint('red', 'Exception while reading page: %s'%e)
        if tries:
          ui._cprint('dark red', 'Retrying...')
          continue
        raise
      break

    a = action_meta()
    if a.valid(self, ui):
      ui._cprint('yellow', 'meta refresh tag detected, following...')
      a.apply(ui, self, None)

  def __str__(self):
    if self.state is None:
      return ''
    return '\n'.join([ "%i: %s"%(i,repr(a)) for (i,a) in enumerate(self.state.list())])

  def getscript(self):
    if self.state is None:
      return None
    return [ x['action'] for x in self.state.list()]

  def __getattribute__(self, name):
    try:
      return object.__getattribute__(self, name)
    except AttributeError:
      return object.__getattribute__(self.state, name)

  def __setattr__(self, name, val):
    if hasattr(self.state, name):
      return self.state.__setattr__(name, val)
    else:
      return object.__setattr__(self, name, val)

def main(ui, script=None, username=None, oldpass=None, newpass=None):
  import json
  import base64
  state = urlvcr(username, oldpass, newpass)
  # If replaying a script, use get_actions_from_script
  if script:
    script = json.loads(script)
    script = json_str(script)
    action_seq = get_actions_from_script(ui, state, script)
  else:
    action_seq = get_actions_ask(ui, state)
  for action in action_seq:
    apply_action(ui, state, action)
  script = state.getscript()
  return json.dumps(script)

def json_str(v):
  def json_str_dict(d):
    n = {}
    for (k,v) in d.items():
      n[json_str(k)] = json_str(v)
    return n
  def json_str_list(v):
    return [ json_str(x) for x in v ]

  if type(v) in (str, unicode):
    return str(v)
  if type(v) == dict:
    return json_str_dict(v)
  if type(v) in (list, tuple):
    return json_str_list(v)
  return v


if __name__ == '__main__':
  #test_expect_groups()
  import ui.ui_tty
  import sys
  import json
  import base64
  import getpass

  ui = ui.ui_tty()

  username=None
  oldpass=None
  newpass=None

  if ui.confirm('Do you have credentials to paste?', False):
    credentials = getpass.getpass('Paste them now and press enter. Echo is off: ')
    credentials = json.loads(base64.decodestring(credentials))
    credentials = json_str(credentials)
    if 'username' in credentials: username=credentials['username']
    if 'oldpass' in credentials: oldpass=credentials['oldpass']
    if 'newpass' in credentials: newpass=credentials['newpass']
  elif ui.confirm('Would you like to encode some now (NOTE: this is not using a secure encoding)?', False):
    username = raw_input('Username: ')
    oldpass = getpass.getpass('OLD Password: ')
    newpass = getpass.getpass('NEW Password: ')
    credentials = {}
    if username: credentials['username'] = username
    if oldpass: credentials['oldpass'] = oldpass
    if newpass: credentials['newpass'] = newpass
    credentials = base64.encodestring(json.dumps(credentials)).replace('\n','')
    ui._print('Credentials: %s'%credentials)

  if len(sys.argv) > 1:
    for script in sys.argv[1:]:
      s = base64.decodestring(script)
      ui._print('Replaying script: %s'%s)
      main(ui, s, username, oldpass, newpass)
  else:
    script = main(ui, None, username, oldpass, newpass)
    if script is not None:
      ui._print('Script\n%s'%script)
      script = base64.encodestring(script).replace('\n','')
      ui._print('Pass this back into the program to replay this script:\n%s'%script)
