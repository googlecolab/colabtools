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

import logging
import os
import sys

from ipykernel import jsonutil
from ipykernel import zmqshell
from IPython.core import interactiveshell
from IPython.core.events import available_events
from ipython_genutils import py3compat

from google.colab import _event_manager
from google.colab import _pip
from google.colab import _shell_customizations
from google.colab import _system_commands


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

  def object_inspect(self, oname, detail_level=0):
    info = self._ofind(oname)
    if info['found'] and sys.getsizeof(info.get('obj', '')) > 5000:
      obj = info.pop('obj')
      info['name'] = oname
      info['string_form'] = (
          _extra_object_info(obj) + '<Object too large to display>')
      info['string_form_abbreviated'] = True
      info['type_name'] = type(obj).__name__
      return info
    result = super(Shell, self).object_inspect(oname, detail_level=detail_level)
    if result.get('string_form', None) is not None:
      result['string_form'] = (
          _extra_object_info(info['obj']) + result['string_form'])
    return result


interactiveshell.InteractiveShellABC.register(Shell)


def _extra_object_info(obj):
  """Return a string with any extra info to include for this object."""
  try:
    # We want to include DataFrame size info, but don't want to raise an
    # exception in the case of a type called `DataFrame` with an unusual shape.
    # We also want to avoid importing pandas, as it's slow to import.
    if type(obj).__name__ == 'DataFrame' and hasattr(obj, 'shape'):
      rows, cols = obj.shape
      # We want this line to be separate from the DataFrame display, so we add
      # *two* newlines to the end.
      #
      # TODO(b/133258663): We also add backticks around the newlines to work
      # around a peculiarity in our markdown quoting; remove this.
      return '{} rows x {} columns`\n\n`'.format(rows, cols)
  except Exception as e:  # pylint: disable=broad-except
    logging.warning('Exception caught during _extra_object_info: %s', e)
  return ''
