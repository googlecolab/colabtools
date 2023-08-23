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
import textwrap
import uuid as _uuid
import weakref as _weakref

from google.colab import _generate_with_variable
from google.colab import _interactive_table_hint_button
from google.colab import _quickchart
from google.colab import output
import IPython as _IPython


_output_callbacks = {}
_MAX_CHART_INSTANCES = 4
_ENABLE_GENERATE = False
_QUICKCHART_BUTTON_MIN_ROW_COUNT = 5  # Min # rows to enable quickchart button.

_ICON_SVG = textwrap.dedent("""
  <svg xmlns="http://www.w3.org/2000/svg" height="24px"viewBox="0 0 24 24"
       width="24px">
      <g>
          <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z"/>
      </g>
  </svg>""")

_HINT_BUTTON_CSS = textwrap.dedent("""
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
""")


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
    self._last_noninteractive_df[key] = df

  def keys(self):
    return list(
        set(self._noninteractive_df_refs.keys()).union(
            set(self._last_noninteractive_df.keys())
        )
    )


_df_cache = DataframeCache()
_chart_cache = {}


def _suggest_charts(df_key):
  """Generates and displays a set of charts from the specified dataframe.

  Args:
    df_key: (str) The dataframe key (element id).
  """
  try:
    df = _df_cache[df_key]
  except KeyError:
    print(
        'WARNING: Runtime no longer has a reference to this dataframe, please'
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
output.register_callback('suggestCharts', _suggest_charts)


def register_df_and_get_html(df):
  df_key = f'df-{str(_uuid.uuid4())}'
  _df_cache[df_key] = df
  return f"""
<div id="{df_key}">
  <button class="colab-df-quickchart" onclick="quickchart('{df_key}')"
            title="Suggest charts."
            style="display:none;">
    {_ICON_SVG}
  </button>
  {_HINT_BUTTON_CSS}
  <script>
    async function quickchart(key) {{
      const charts = await google.colab.kernel.invokeFunction(
          'suggestCharts', [key], {{}});
    }}
    (() => {{
      let quickchartButtonEl =
        document.querySelector('#{df_key} button');
      quickchartButtonEl.style.display =
        google.colab.kernel.accessAllowed ? 'block' : 'none';
    }})();
  </script>
</div>"""


def _df_formatter_with_hint_buttons(df):
  """Alternate df formatter with buttons for interactive and quickchart."""
  buttons = []
  if len(df) >= _QUICKCHART_BUTTON_MIN_ROW_COUNT:
    buttons.append(register_df_and_get_html(df))
  if _ENABLE_GENERATE:
    buttons.append(_generate_with_variable.get_html(df))
  # pylint: disable=protected-access
  html = _interactive_table_hint_button._df_formatter_with_interactive_hint(
      df, buttons
  )
  return textwrap.dedent(html)


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
