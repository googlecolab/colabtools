# Copyright 2021 Google Inc.
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
"""Formatter used to display a data table conversion button next to dataframes."""

import textwrap

from google.colab import _generate_with_variable
from google.colab import _interactive_table_hint_button
import IPython as _IPython


_ENABLE_GENERATE = False


def _df_formatter_with_hint_buttons(df):
  """Alternate df formatter with buttons for interactive."""

  buttons = []
  if _ENABLE_GENERATE:
    buttons.append(_generate_with_variable.get_html(df))
  # pylint: disable=protected-access
  html = _interactive_table_hint_button._df_formatter_with_interactive_hint(
      df, buttons
  )
  return textwrap.dedent(html)


_original_formatters = {}


def _enable_df_interactive_hint_formatter():
  """Formatter that surfaces interactive tables to user."""

  shell = _IPython.get_ipython()
  if not shell:
    return
  key = 'text/html'
  if key not in _original_formatters:
    formatters = shell.display_formatter.formatters
    _original_formatters[key] = formatters[key].for_type_by_name(
        'pandas.core.frame', 'DataFrame', _df_formatter_with_hint_buttons
    )


def _disable_df_interactive_hint_formatter():
  """Restores the original html formatter for Pandas DataFrames."""
  shell = _IPython.get_ipython()
  if not shell:
    return
  key = 'text/html'
  if key in _original_formatters:
    formatters = shell.display_formatter.formatters
    formatters[key].pop('pandas.core.frame.DataFrame', None)
    formatters[key].for_type_by_name(
        'pandas.core.frame', 'DataFrame', _original_formatters.pop(key)
    )
