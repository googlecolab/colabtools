# Copyright 2017 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Colab-specific shell customizations."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import __future__
import datetime
import os
import sys
import traceback

from ipykernel import jsonutil
from ipykernel import zmqshell
from IPython.core import alias
from IPython.core import inputsplitter
from IPython.core import interactiveshell
from IPython.core import oinspect
from IPython.core.events import available_events
from IPython.utils import PyColorize
from ipython_genutils import py3compat

from google.colab import _event_manager
from google.colab import _history
from google.colab import _inspector
from google.colab import _pip
from google.colab import _shell_customizations
from google.colab import _system_commands


# Python doesn't expose a name in builtins for a getset descriptor attached to a
# python class implemented in C, eg an entry in this array:
#   https://docs.python.org/3/c-api/typeobj.html#c.PyTypeObject.tp_getset
#
# We punt and use a known example of such a descriptor.
_GetsetDescriptorType = type(datetime.datetime.year)


# The code below warns the user that a runtime restart is necessary if a
# package that is already imported is pip installed. Setting the
# SKIP_COLAB_PIP_WARNING environment variable will disable this warning.
def _show_pip_warning():
  return os.environ.get('SKIP_COLAB_PIP_WARNING', '0') == '0'


class Shell(zmqshell.ZMQInteractiveShell):
  """Shell with additional Colab-specific features."""

  def init_events(self):
    self.events = _event_manager.ColabEventManager(self, available_events)
    self.events.register('pre_execute', self._clear_warning_registry)

  def init_inspector(self):
    """Initialize colab's custom inspector."""
    self.inspector = _inspector.ColabInspector(oinspect.InspectColors,
                                               PyColorize.ANSICodeColors,
                                               'NoColor',
                                               self.object_info_string_level)

  def init_history(self):
    """Initialize colab's custom history manager."""
    self.history_manager = _history.ColabHistoryManager(shell=self, parent=self)
    self.configurables.append(self.history_manager)

  def _should_use_native_system_methods(self):
    return os.getenv('USE_NATIVE_IPYTHON_SYSTEM_COMMANDS', False)

  def getoutput(self, *args, **kwargs):
    if self._should_use_native_system_methods():
      return super(Shell, self).getoutput(*args, **kwargs)

    output = _system_commands._getoutput_compat(self, *args, **kwargs)  # pylint:disable=protected-access

    if _show_pip_warning() and _pip.is_pip_install_command(*args, **kwargs):
      _pip.print_previous_import_warning(output.nlstr)

    return output

  def system(self, *args, **kwargs):
    if self._should_use_native_system_methods():
      return super(Shell, self).system(*args, **kwargs)

    pip_warn = _show_pip_warning() and _pip.is_pip_install_command(
        *args, **kwargs)

    if pip_warn:
      kwargs.update({'also_return_output': True})

    output = _system_commands._system_compat(self, *args, **kwargs)  # pylint:disable=protected-access

    if pip_warn:
      _pip.print_previous_import_warning(output)

  def _send_error(self, exc_content):
    topic = (self.displayhook.topic.replace(b'execute_result', b'err') if
             self.displayhook.topic else None)
    self.displayhook.session.send(
        self.displayhook.pub_socket,
        u'error',
        jsonutil.json_clean(exc_content),
        self.displayhook.parent_header,
        ident=topic)

  def _showtraceback(self, etype, evalue, stb):
    # This override is largely the same as the base implementation with special
    # handling to provide error_details in the response if a ColabErrorDetails
    # item was passed along.
    sys.stdout.flush()
    sys.stderr.flush()

    error_details = None
    if isinstance(stb, _shell_customizations.ColabTraceback):
      colab_tb = stb
      error_details = colab_tb.error_details
      stb = colab_tb.stb

    exc_content = {
        'traceback': stb,
        'ename': py3compat.unicode_type(etype.__name__),
        'evalue': py3compat.safe_unicode(evalue),
    }

    if error_details:
      exc_content['error_details'] = error_details
    self._send_error(exc_content)
    self._last_traceback = stb

  # We want to customize the behavior of `_ofind` and `_getattr_property` around
  # handling of attribute descriptors defined in C; this method and the one
  # below are slightly modified copies of the version upstream:
  #   https://github.com/ipython/ipython/blob/5be56c736c794d7ba597394a16a670ef17d0558d/IPython/core/interactiveshell.py#L1374-L1512
  def _ofind(self, oname, namespaces=None):
    """Find an object in the available namespaces.

    self._ofind(oname) -> dict with keys: found,obj,ospace,ismagic

    Has special code to detect magic functions.

    Args:
      oname: Name to look up.
      namespaces: A list of additional namespaces to search.

    Returns:
      Information about the object.
    """
    oname = oname.strip()
    # print '1- oname: <%r>' % oname  # dbg
    if (not oname.startswith(inputsplitter.ESC_MAGIC) and
        not oname.startswith(inputsplitter.ESC_MAGIC2) and
        not py3compat.isidentifier(oname, dotted=True)):
      return dict(found=False)

    if namespaces is None:
      # Namespaces to search in:
      # Put them in a list. The order is important so that we
      # find things in the same order that Python finds them.
      namespaces = [
          ('Interactive', self.user_ns),
          ('Interactive (global)', self.user_global_ns),
          ('Python builtin', py3compat.builtin_mod.__dict__),
      ]

    # initialize results to 'null'
    found = False
    obj = None
    ospace = None
    ismagic = False
    isalias = False
    parent = None

    # We need to special-case 'print', which as of python2.6 registers as a
    # function but should only be treated as one if print_function was
    # loaded with a future import.  In this case, just bail.
    if (oname == 'print' and not py3compat.PY3 and
        not (self.compile.compiler_flags
             & __future__.CO_FUTURE_PRINT_FUNCTION)):
      return {
          'found': found,
          'obj': obj,
          'namespace': ospace,
          'ismagic': ismagic,
          'isalias': isalias,
          'parent': parent
      }

    # Look for the given name by splitting it in parts.  If the head is
    # found, then we look for all the remaining parts as members, and only
    # declare success if we can find them all.
    oname_parts = oname.split('.')
    oname_head, oname_rest = oname_parts[0], oname_parts[1:]
    for nsname, ns in namespaces:
      try:
        obj = ns[oname_head]
      except KeyError:
        continue
      else:
        # print 'oname_rest:', oname_rest  # dbg
        for idx, part in enumerate(oname_rest):
          try:
            parent = obj
            # The last part is looked up in a special way to avoid
            # descriptor invocation as it may raise or have side
            # effects.
            if idx == len(oname_rest) - 1:
              obj = self._getattr_property(obj, part)
            else:
              obj = getattr(obj, part)
          except:  # pylint: disable=bare-except
            # Blanket except b/c some badly implemented objects
            # allow __getattr__ to raise exceptions other than
            # AttributeError, which then crashes IPython.
            break
        else:
          # If we finish the for loop (no break), we got all members
          found = True
          ospace = nsname
          break  # namespace loop

    # Try to see if it's magic
    if not found:
      obj = None
      if oname.startswith(inputsplitter.ESC_MAGIC2):
        oname = oname.lstrip(inputsplitter.ESC_MAGIC2)
        obj = self.find_cell_magic(oname)
      elif oname.startswith(inputsplitter.ESC_MAGIC):
        oname = oname.lstrip(inputsplitter.ESC_MAGIC)
        obj = self.find_line_magic(oname)
      else:
        # search without prefix, so run? will find %run?
        obj = self.find_line_magic(oname)
        if obj is None:
          obj = self.find_cell_magic(oname)
      if obj is not None:
        found = True
        ospace = 'IPython internal'
        ismagic = True
        isalias = isinstance(obj, alias.Alias)

    # Last try: special-case some literals like '', [], {}, etc:
    if not found and oname_head in ["''", '""', '[]', '{}', '()']:
      obj = eval(oname_head)  # pylint: disable=eval-used
      found = True
      ospace = 'Interactive'

    return {
        'found': found,
        'obj': obj,
        'namespace': ospace,
        'ismagic': ismagic,
        'isalias': isalias,
        'parent': parent
    }

  @staticmethod
  def _getattr_property(obj, attrname):
    """Property-aware getattr to use in object finding.

    If attrname represents a property, return it unevaluated (in case it has
    side effects or raises an error.

    Args:
      obj: Object to look up an attribute on.
      attrname: Name of the attribute to look up.

    Returns:
      An attribute from either the object or its type.
    """
    if not isinstance(obj, type):
      try:
        # `getattr(type(obj), attrname)` is not guaranteed to return
        # `obj`, but does so for property:
        #
        # property.__get__(self, None, cls) -> self
        #
        # The universal alternative is to traverse the mro manually
        # searching for attrname in class dicts.
        attr = getattr(type(obj), attrname)
      except AttributeError:
        pass
      else:
        # This relies on the fact that data descriptors (with both
        # __get__ & __set__ magic methods) take precedence over
        # instance-level attributes:
        #
        #    class A(object):
        #        @property
        #        def foobar(self): return 123
        #    a = A()
        #    a.__dict__['foobar'] = 345
        #    a.foobar  # == 123
        #
        # So, a property may be returned right away.
        if isinstance(attr, (property, _GetsetDescriptorType)):
          return attr

    # Nothing helped, fall back.
    return getattr(obj, attrname)

  def object_inspect(self, oname, detail_level=0):
    info = self._ofind(oname)

    if info['found']:
      try:
        info = self._object_find(oname)
        # We need to avoid arbitrary python objects remaining in info (and
        # potentially being serialized below); `obj` itself needs to be
        # removed, but retained for use below, and `parent` isn't used at all.
        obj = info.pop('obj', '')
        info.pop('parent', '')
        result = self.inspector.info(
            obj, oname, info=info, detail_level=detail_level)
      except Exception as e:  # pylint: disable=broad-except
        self.kernel.log.info('Exception caught during object inspection: '
                             '{!r}\nTraceback:\n{}'.format(
                                 e, ''.join(
                                     traceback.format_tb(sys.exc_info()[2]))))
    else:
      result = super(Shell, self).object_inspect(
          oname, detail_level=detail_level)
    return result


interactiveshell.InteractiveShellABC.register(Shell)
