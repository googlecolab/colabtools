# Copyright 2023 Google Inc.
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
"""Colab automatic visualization libraries and utilities."""
from google.colab import _quickchart
from google.colab import _quickchart_lib

__all__ = ['quickchart', 'get_df', 'MplChart']


def quickchart(df):
  """Renders a set of charts that can be visualized from the given dataframe.

  Programmatic chart generation api equivalent to invoking the quickchart button
  displayed next to dataframes in the cell output frame.

  Args:
    df: (pd.DataFrame) A dataframe.
  """
  for chart_section in _quickchart.find_charts(df):
    chart_section.display()


get_df = _quickchart.get_df

MplChart = _quickchart_lib.MplChart
