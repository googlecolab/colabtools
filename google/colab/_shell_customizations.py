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

import textwrap

from IPython.utils import coloransi
from google.colab import _ipython as ipython


_GREEN = coloransi.TermColors.Green
_RED = coloransi.TermColors.Red
_NORMAL = coloransi.TermColors.Normal


def initialize():
  ip = ipython.get_ipython()
  if ip:
    _CustomErrorHandlers(ip)


class FormattedTracebackError(Exception):

  def __init__(self, message, custom_message):
    super(FormattedTracebackError, self).__init__(message)
    self._full_traceback = custom_message

  def _render_traceback_(self):
    return self._full_traceback


class _CustomErrorHandlers(object):
  """Custom error handler for the IPython shell.

  Helps to add a _render_traceback_ method for errors that can't be wrapped
  since they're too low-level (i.e. ImportError).
  """

  def __init__(self, shell):
    self.custom_message_getters = {
        ImportError: _CustomErrorHandlers.import_message,
    }
    shell.set_custom_exc(
        tuple(self.custom_message_getters.keys()), self.handle_error)

  def handle_error(self, shell, etype, exception, tb, tb_offset=None):
    """Invoked when the shell catches an error in custom_message_getters."""
    if etype in self.custom_message_getters:
      message = str(exception)
      custom_message = self.custom_message_getters[etype](message)
      if custom_message:
        structured_traceback = shell.InteractiveTB.structured_traceback(
            etype, exception, tb, tb_offset=tb_offset)
        # Ensure a blank line appears between the standard traceback and custom
        # error messaging.
        formatted_traceback_lines = structured_traceback + ['', custom_message]
        wrapped = FormattedTracebackError(message, formatted_traceback_lines)
        return shell.showtraceback(exc_tuple=(etype, wrapped, tb))
    return shell.showtraceback()

  @staticmethod
  def import_message(_):
    """Return a helpful message for failed imports."""
    sep = _RED + '-' * 75

    # TODO(b/68989501): Investigate displaying the example notebook link in a
    # button, similar to our "Search StackOverflow" button.
    return textwrap.dedent("""\
        {sep}{green}
        NOTE: If your import is failing due to a missing package, you can
        manually install dependencies using either !pip or !apt.

        Examples of installing some common dependencies can be found at:
        https://colab.research.google.com/notebook#fileId=/v2/external/notebooks/snippets/importing_libraries.ipynb
        {sep}{normal}\n""".format(sep=sep, green=_GREEN, normal=_NORMAL))
