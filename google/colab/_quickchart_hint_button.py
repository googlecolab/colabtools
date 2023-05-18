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

import logging
import uuid as _uuid
import weakref as _weakref

from google.colab import _interactive_table_hint_button
from google.colab import _quickchart
from google.colab import output
import IPython as _IPython


_output_callbacks = {}
_MAX_CHART_INSTANCES = 4

_ICON_SVG = """
  <svg xmlns="http://www.w3.org/2000/svg" height="24px"viewBox="0 0 24 24"
       width="24px">
      <g>
          <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z"/>
      </g>
  </svg>"""

_HINT_BUTTON_CSS = """
  <style>
    .colab-df-quickchart {
      background-color: #E8F0FE;
      border: none;
      border-radius: 50%;
      cursor: pointer;
      display: none;
      fill: #1967D2;
      height: 32px;
      padding: 0 0 0 0;
      width: 32px;
    }

    .colab-df-quickchart:hover {
      background-color: #E2EBFA;
      box-shadow: 0px 1px 2px rgba(60, 64, 67, 0.3), 0px 1px 3px 1px rgba(60, 64, 67, 0.15);
      fill: #174EA6;
    }

    [theme=dark] .colab-df-quickchart {
      background-color: #3B4455;
      fill: #D2E3FC;
    }

    [theme=dark] .colab-df-quickchart:hover {
      background-color: #434B5C;
      box-shadow: 0px 1px 3px 1px rgba(0, 0, 0, 0.15);
      filter: drop-shadow(0px 1px 2px rgba(0, 0, 0, 0.3));
      fill: #FFFFFF;
    }
  </style>
"""


class DataframeCache(object):
  """Cache of dataframes that may be requested for output visualization.

  Purposely uses weakref to allow memory to be freed for dataframes which are no
  longer referenced elsewhere, rather than accumulating all dataframes seen so
  far.
  """

  def __init__(self):
    """Constructor."""
    # Cache of non-interactive dfs that still have live references and could be
    # printed as interactive dfs.
    self._noninteractive_df_refs = _weakref.WeakValueDictionary()
    # Single entry cache that stores a shallow copy of the last printed df.
    self._last_noninteractive_df = {}

  def __getitem__(self, key):
    """Gets a dataframe by the given key if it still exists."""
    if key in self._last_noninteractive_df:
      return self._last_noninteractive_df.pop(key)
    elif key in self._noninteractive_df_refs:
      return self._noninteractive_df_refs.pop(key)
    raise KeyError('Dataframe key "%s" was not found' % key)

  def __setitem__(self, key, df):
    """Adds the given dataframe to the cache."""
    self._noninteractive_df_refs[key] = df

    # Ensure our last value cache only contains one item.
    self._last_noninteractive_df.clear()
    self._last_noninteractive_df[key] = df.copy(deep=False)

  def keys(self):
    return list(self._noninteractive_df_refs.keys()) + list(
        self._last_noninteractive_df.keys()
    )


_df_cache = DataframeCache()
_chart_cache = {}


def generate_charts(df_key):
  """Generates and displays a set of charts from the specified dataframe.

  Args:
    df_key: (str) The dataframe key (element id).
  """
  try:
    df = _df_cache[df_key]
  except KeyError:
    print(
        'Error: Runtime no longer has a reference to this dataframe, please'
        ' re-run this cell and try again.'
    )
    return

  for chart_section in _quickchart.find_charts(
      df, max_chart_instances=_MAX_CHART_INSTANCES
  ):
    for chart in chart_section.charts:
      _chart_cache[chart.chart_id] = chart
    chart_section.display()


def _get_code_for_chart(chart_key):
  if chart_key in _chart_cache:
    chart_code = _chart_cache[chart_key].get_code()
    return _IPython.display.JSON(dict(code=chart_code))
  else:
    logging.error('Did not find quickchart key %s in chart cache', chart_key)
    return f'Could not find code for chart {chart_key}'


output.register_callback('getCodeForChart', _get_code_for_chart)


def _df_formatter_with_hint_buttons(df):
  """Alternate df formatter with buttons for interactive and quickchart."""
  # pylint: disable=protected-access
  df_key = 'df-' + str(_uuid.uuid4())
  _df_cache[df_key] = df
  interactive_html = (
      _interactive_table_hint_button._df_formatter_with_interactive_hint(df)
  )

  callback_name = 'generateCharts'
  if callback_name not in _output_callbacks:
    _output_callbacks[callback_name] = output.register_callback(
        callback_name, generate_charts
    )

  quickchart_html = _get_html(df_key)
  style_index = interactive_html.find('<style>')
  return (
      interactive_html[:style_index]
      + quickchart_html
      + interactive_html[style_index:]
  )


def _get_html(key):
  return """
    <div id="{key}">
      <button class="colab-df-quickchart" onclick="quickchart('{key}')"
              title="Generate charts."
              style="display:none;">
        {icon}
      </button>
    </div>
    {css}
    <script>
      const quickchartButtonEl =
        document.querySelector('#{key} button.colab-df-quickchart');
      quickchartButtonEl.style.display =
        google.colab.kernel.accessAllowed ? 'block' : 'none';

      async function quickchart(key) {{
        const containerElement = document.querySelector('#{key}');
        const charts = await google.colab.kernel.invokeFunction(
            'generateCharts', [key], {{}});
      }}
    </script>
  """.format(
      css=_HINT_BUTTON_CSS,
      icon=_ICON_SVG,
      key=key,
  )


_original_formatters = {}


def _enable_df_interactive_hint_formatter():
  """Formatter that surfaces interactive tables and quickchart to user."""
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
