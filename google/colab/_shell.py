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

import os
import sys

from ipykernel import jsonutil
from ipykernel import zmqshell
from IPython.core import interactiveshell
from ipython_genutils import py3compat

from google.colab import _shell_customizations
from google.colab import _system_commands


class Shell(zmqshell.ZMQInteractiveShell):
  """Shell with additional Colab-specific features."""

  def _should_use_native_system_methods(self):
    return os.getenv('USE_NATIVE_IPYTHON_SYSTEM_COMMANDS', False)

  def getoutput(self, *args, **kwargs):
    if self._should_use_native_system_methods():
      return super(Shell, self).getoutput(*args, **kwargs)

    return _system_commands._getoutput_compat(self, *args, **kwargs)  # pylint:disable=protected-access

  def system(self, *args, **kwargs):
    if self._should_use_native_system_methods():
      return super(Shell, self).system(*args, **kwargs)

    return _system_commands._system_compat(self, *args, **kwargs)  # pylint:disable=protected-access

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


interactiveshell.InteractiveShellABC.register(Shell)
