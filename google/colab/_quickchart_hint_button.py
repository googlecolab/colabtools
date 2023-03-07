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

from google.colab import _interactive_table_hint_button
from google.colab import _quickchart
from google.colab import output
import IPython as _IPython

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


def generate_charts(df_key):
  """Generates and displays a set of charts from the specified dataframe.

  Args:
    df_key: (str) The dataframe key (element id).
  """
  # pylint: disable=protected-access
  df = _interactive_table_hint_button._get_dataframe(df_key)
  if df is None:
    return
  for chart in _quickchart.find_charts(
      df, max_chart_instances=_MAX_CHART_INSTANCES
  ):
    chart.display()


_output_callbacks = {}


def _df_formatter_with_hint_buttons(dataframe):
  """Alternate df formatter with buttons for interactive and quickchart."""
  # pylint: disable=protected-access
  interactive_html = (
      _interactive_table_hint_button._df_formatter_with_interactive_hint(
          dataframe
      )
  )
  key = _interactive_table_hint_button._get_last_dataframe_key()

  callback_name = 'generateCharts'
  if callback_name not in _output_callbacks:
    _output_callbacks[callback_name] = output.register_callback(
        callback_name, generate_charts
    )

  quickchart_html = _get_html(key)
  style_index = interactive_html.find('<style>')
  return (
      interactive_html[:style_index]
      + quickchart_html
      + interactive_html[style_index:]
  )


def _get_html(key):
  return """
    <button class="colab-df-quickchart" onclick="quickchart('{key}')"
            title="Generate charts."
            style="display:none;">
      {icon}
    </button>
   {css}
    <script>
      const quickchartButtonEl =
        document.querySelector('#{key} button.colab-df-quickchart');
      quickchartButtonEl.style.display =
        google.colab.kernel.accessAllowed ? 'block' : 'none';

      async function quickchart(key) {{
        const containerElement = document.querySelector('#{key}');
        const charts = await google.colab.kernel.invokeFunction(
            'generateCharts', [key], {{}})
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
