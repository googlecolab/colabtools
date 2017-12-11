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


class ColabTraceback(object):

  def __init__(self, stb, error_details):
    self.stb = stb
    self.error_details = error_details


class FormattedTracebackError(Exception):

  def __init__(self, message, stb, details):
    super(FormattedTracebackError, self).__init__(message)
    self._colab_traceback = ColabTraceback(stb, details)

  def _render_traceback_(self):
    return self._colab_traceback


class _CustomErrorHandlers(object):
  """Custom error handler for the IPython shell.

  Allows us to add custom messaging for certain error types (i.e. ImportError).
  """

  def __init__(self, shell):
    # The values for this map are functions which return
    # (custom_message, additional error details).
    self.custom_error_handlers = {
        ImportError: _CustomErrorHandlers.import_message,
    }
    shell.set_custom_exc(
        tuple(self.custom_error_handlers.keys()), self.handle_error)

  def handle_error(self, shell, etype, exception, tb, tb_offset=None):
    """Invoked when the shell catches an error in custom_message_getters."""
    if etype in self.custom_error_handlers:
      message = str(exception)
      result = self.custom_error_handlers[etype](message)
      if result:
        custom_message, details = result
        structured_traceback = shell.InteractiveTB.structured_traceback(
            etype, exception, tb, tb_offset=tb_offset)
        # Ensure a blank line appears between the standard traceback and custom
        # error messaging.
        structured_traceback += ['', custom_message]
        wrapped = FormattedTracebackError(message, structured_traceback,
                                          details)
        return shell.showtraceback(exc_tuple=(etype, wrapped, tb))
    return shell.showtraceback()

  @staticmethod
  def import_message(_):
    """Return a helpful message for failed imports."""
    sep = _RED + '-' * 75

    msg = textwrap.dedent("""\
        {sep}{green}
        NOTE: If your import is failing due to a missing package, you can
        manually install dependencies using either !pip or !apt.

        To view examples of installing some common dependencies, click the
        "Open Examples" button below.
        {sep}{normal}\n""".format(sep=sep, green=_GREEN, normal=_NORMAL))

    details = {
        'actions': [
            {
                'action':
                    'open_url',
                'action_text':
                    'Open Examples',
                'url':
                    '/notebook#fileId=/v2/external/notebooks/snippets/importing_libraries.ipynb',  # pylint:disable=line-too-long
            },
        ],
    }
    return msg, details
