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

import re
import textwrap

from IPython.utils import coloransi
from google.colab import _ipython as ipython


_GREEN = coloransi.TermColors.Green
_RED = coloransi.TermColors.Red
_NORMAL = coloransi.TermColors.Normal
_SEP = _RED + '-' * 75

# Set of modules that have snippets explaining how they can be installed. Any
# ImportErrors for modules in this set will show a custom error message pointing
# to the snippet.
SNIPPET_MODULES = set([
    'cartopy',
    'libarchive',
    'pydot',
    'torch',
])


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

  def _get_error_handler(self, etype):
    for handled_type in self.custom_error_handlers:
      if issubclass(etype, handled_type):
        return self.custom_error_handlers[handled_type]
    return None

  def handle_error(self, shell, etype, exception, tb, tb_offset=None):
    """Invoked when the shell catches an error in custom_message_getters."""
    handler = self._get_error_handler(etype)
    if not handler:
      return shell.showtraceback()

    result = handler(exception)
    if result:
      custom_message, details = result
      structured_traceback = shell.InteractiveTB.structured_traceback(
          etype, exception, tb, tb_offset=tb_offset)
      # Ensure a blank line appears between the standard traceback and custom
      # error messaging.
      structured_traceback += ['', custom_message]
      wrapped = FormattedTracebackError(
          str(exception), structured_traceback, details)
      return shell.showtraceback(exc_tuple=(etype, wrapped, tb))

  @staticmethod
  def import_message(error):
    """Return a helpful message for failed imports."""
    # Python 3 ModuleNotFoundErrors have a "name" attribute. Preferring this
    # over regex matching if the attribute is available.
    module_name = getattr(error, 'name', None)
    if not module_name:
      match = re.search(r'No module named \'?(?P<name>[a-zA-Z0-9_\.]+)\'?',
                        str(error))
      module_name = match.groupdict()['name'].split('.')[0] if match else None

    if module_name in SNIPPET_MODULES:
      msg = textwrap.dedent("""\
        {sep}{green}
        NOTE: If your import is failing due to a missing package, you can
        manually install dependencies using either !pip or !apt.

        To install {snippet}, click the button below.
        {sep}{normal}\n""".format(
            sep=_SEP, green=_GREEN, normal=_NORMAL, snippet=module_name))
      details = {
          'actions': [
              {
                  'action': 'open_snippet',
                  'action_text': 'Install {}'.format(module_name),
                  # Snippets for installing a custom library always end with
                  # an import of the library itself.
                  'snippet_filter': 'import {}'.format(module_name),
              },
          ],
      }
      return msg, details

    msg = textwrap.dedent("""\
        {sep}{green}
        NOTE: If your import is failing due to a missing package, you can
        manually install dependencies using either !pip or !apt.

        To view examples of installing some common dependencies, click the
        "Open Examples" button below.
        {sep}{normal}\n""".format(sep=_SEP, green=_GREEN, normal=_NORMAL))

    details = {
        'actions': [{
            'action': 'open_url',
            'action_text': 'Open Examples',
            'url': '/notebooks/snippets/importing_libraries.ipynb',
        },],
    }
    return msg, details


def compute_completion_metadata(shell, matches):
  """Computes completion item metadata.

  Args:
    shell: IPython shell
    matches: List of string completion matches.

  Returns:
    Metadata for each of the matches.
  """

  # We want to temporarily change the default level of detail returned by the
  # inspector, to avoid slow completions (cf b/112153563).
  old_str_detail_level = shell.inspector.str_detail_level
  shell.inspector.str_detail_level = 1
  try:
    infos = []
    for match in matches:
      info = {}
      if '#' in match:
        # Runtime type information added by customization._add_type_information.
        info['type_name'] = match.split('#')[1]
      else:
        inspect_results = shell.object_inspect(match)
        # Use object_inspect to find the type and filter to only what is needed
        # since there can be a lot of completions to send.
        info['type_name'] = inspect_results['type_name']
        if inspect_results['definition']:
          info['definition'] = inspect_results['definition']
        elif inspect_results['init_definition']:
          info['definition'] = inspect_results['init_definition']
      infos.append(info)
    return infos
  finally:
    shell.inspector.str_detail_level = old_str_detail_level
