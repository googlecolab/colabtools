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

import datetime
import os
import pathlib
import sys

from google.colab import _history
from google.colab import _inspector
from google.colab import _pip
from google.colab import _shell_customizations
from google.colab import _system_commands
from ipykernel import compiler
from ipykernel import jsonutil
from ipykernel import zmqshell
from IPython.core import interactiveshell
from IPython.core import oinspect
from IPython.utils import PyColorize
from ipython_genutils import py3compat

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


class _ColabXCachingCompiler(compiler.XCachingCompiler):
  """An XCachingCompiler that uses some form of the old IPython code_name.

  This is a transitionary class that will be removed once we've fully migrated
  to the new form of the code_name.

  For enhanced debugging, ipykernel compiler defines a new XCachingCompiler:
  https://github.com/ipython/ipykernel/blob/v6.17.1/ipykernel/compiler.py#L91

  It's used as the default IPythonKernel shell_class' compiler_class:
  https://github.com/ipython/ipykernel/blob/v6.17.1/ipykernel/ipkernel.py#L96

  This means, functionally, the `code_name` has changed to
  something like /tmp/ipykernel_{pid}/{murmurhash}.py, rather than
  <ipython-N-XXXXX.py>.
  https://github.com/ipython/ipykernel/blob/v6.17.1/ipykernel/compiler.py#L75

  Since we implement our own Shell which inherits from
  `zmqshell.ZMQInteractiveShell`, which inherits from
  `IPython.core.interactiveshell.InteractiveShell`, we pick up this change.
  The old code_name (e.g. `ipython-N-XXXXX.py`) is widely used and parsed.
  We therefore update our shell to partially match the old behavior.
  """

  def get_code_name(self, raw_code, code, number):
    """Returns a custom code name that mostly matches old behavior.

    This is a transitionary method that will be removed once we've fully
    migrated to the new form of the code_name. It converts over to use the
    XCachingCompiler's code_name method and use of murmurhash, but then
    reformats the code_name to match the old behavior. This will give some
    incremental insight to goldens and other brittle code that we'll have to
    update in subsequent steps of the migration.

    Args:
      raw_code: The raw code.
      code: The code.
      number: Treated as the execution count in Colab.
    """
    code_name = super().get_code_name(raw_code, code, number)
    if code_name.endswith('.py'):
      path = pathlib.Path(code_name)
      code_name = f'/tmp/ipython-input-{number}-{path.name}'
    return code_name


class Shell(zmqshell.ZMQInteractiveShell):
  """Shell with additional Colab-specific features."""

  def init_inspector(self):
    """Initialize colab's custom inspector."""
    self.inspector = _inspector.ColabInspector(
        oinspect.InspectColors,
        PyColorize.ANSICodeColors,
        'NoColor',
        self.object_info_string_level,
    )

  def init_history(self):
    """Initialize colab's custom history manager."""
    self.history_manager = _history.ColabHistoryManager(shell=self, parent=self)
    self.configurables.append(self.history_manager)

  def init_instance_attrs(self):
    """Initialize instance attributes."""
    self.compiler_class = _ColabXCachingCompiler
    super().init_instance_attrs()

  def _should_use_native_system_methods(self):
    # TODO: b/277214888 - Update to match intended values, as appropriate.
    return bool(os.getenv('USE_NATIVE_IPYTHON_SYSTEM_COMMANDS'))

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
        *args, **kwargs
    )

    if pip_warn:
      kwargs.update({'also_return_output': True})

    output = _system_commands._system_compat(self, *args, **kwargs)  # pylint:disable=protected-access

    if pip_warn:
      _pip.print_previous_import_warning(output)

  def _send_error(self, exc_content):
    topic = (
        self.displayhook.topic.replace(b'execute_result', b'err')
        if self.displayhook.topic
        else None
    )
    self.displayhook.session.send(
        self.displayhook.pub_socket,
        'error',
        jsonutil.json_clean(exc_content),
        self.displayhook.parent_header,
        ident=topic,
    )

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

  # We want to customize the behavior of `_getattr_property` around handling of
  # attribute descriptors defined in C; this method and the one below are
  # slightly modified copies of the version upstream:
  #   https://github.com/ipython/ipython/blob/5be56c736c794d7ba597394a16a670ef17d0558d/IPython/core/interactiveshell.py#L1374-L1512
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
        #    class A:
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

  def run_cell_magic(self, magic_name, line, cell):
    # We diverge from Jupyter behavior here: we want to allow cell magics with a
    # nonempty line and no cell to execute, to unblock users executing a cell
    # like:
    # %%mymagic --help
    if line and not cell:
      cell = ' '
    return super().run_cell_magic(magic_name, line, cell)


interactiveshell.InteractiveShellABC.register(Shell)
