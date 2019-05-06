# Copyright 2019 Google Inc.
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
"""Interactive table for displaying pandas dataframes.

Example:

  from google.colab.data_table import DataTable
  from vega_datasets import data
  airports = data.airports()  # DataFrame
  DataTable(airports)  # Displays as interactive table
"""
from __future__ import absolute_import as _
from __future__ import division as _
from __future__ import print_function as _

import json as _json
import traceback as _traceback
import uuid as _uuid
import IPython as _IPython
import six as _six

from google.colab import _interactive_table_helper

__all__ = [
    'DataTable', 'enable_dataframe_formatter', 'disable_dataframe_formatter'
]

GVIZ_JS = 'https://ssl.gstatic.com/colaboratory/data_table/ff215576a37b3124/data_table.js'

#  pylint:disable=g-import-not-at-top
#  pylint:disable=g-importing-member
if _six.PY2:
  from cgi import escape as _escape
else:
  from html import escape as _escape
#  pylint:enable=g-importing-member
#  pylint:enable=g-import-not-at-top


def _force_to_latin1(x):
  return 'nonunicode data: %s...' % _escape(x[:100].decode('latin1'))


_DEFAULT_NONUNICODE_FORMATTER = _force_to_latin1
if _six.PY2:
  _DEFAULT_FORMATTERS = {unicode: lambda x: x.encode('utf8')}
else:
  _DEFAULT_FORMATTERS = {str: lambda x: x}


class DataTable(_IPython.display.DisplayObject):
  """An interactive data table display."""

  @classmethod
  def formatter(cls, dataframe, **kwargs):
    return cls(dataframe, **kwargs)._repr_html_()  # pylint: disable=protected-access

  def __init__(self,
               dataframe,
               include_index=True,
               num_rows_per_page=30,
               max_rows=20000,
               max_columns=20):
    """Constructor.

    Args:
       dataframe: the dataframe source for the table
       include_index: boolean specifying whether index should be included.
       num_rows_per_page: display that many rows per page initially. uses
         _DEFAULT_ROWS_PER_PAGE if not provided.
       max_rows: if len(data) exceeds this value a warning will be printed and
         the table truncated. Uses _DEFAULT_MAX_ROWS if not provided
       max_columns: if len(columns) exceeds this value a warning will be printed
         and truncated. Uses _DEFAULT_MAX_COLUMNS if not provided
    """
    self._dataframe = dataframe
    self._include_index = include_index
    self._num_rows_per_page = num_rows_per_page
    self._max_rows = max_rows
    self._max_columns = max_columns

  def _repr_html_(self):
    """Used by frontend to generate the actual table.

    Returns:

    html representation and javascript hooks to generate the table.
    """
    dataframe = self._dataframe.iloc[:self._max_rows, :self._max_columns]

    if self._include_index or dataframe.shape[1] == 0:
      dataframe = dataframe.reset_index()
    if not dataframe.columns.is_unique:
      df_copy = dataframe.copy(deep=False)
      df_copy.columns = range(dataframe.shape[1])
      records = df_copy.to_records(index=False)
      dataframe = records[[str(n) for n in list(records.dtype.names)]]

    id_ = 'IT_' + str(_uuid.uuid4())

    # implicit evalution of numpy.array into bool.  bad idea!
    if dataframe.size == 0:
      return 'The table is empty'
    try:
      # TODO(b/129873703): Convert this to load the interactive table script as
      # a module. This can occur after the binary has been updated to
      # https://ssl.gstatic.com/colaboratory/data_table/496e58d5602d9b04/data_table.js
      return ('<script src="{gviz_url}"></script>'
              '<div id="{id}"></div>'
              '<script>{js_code}</script>').format(
                  gviz_url=GVIZ_JS,
                  id=id_,
                  js_code=self._gen_js(dataframe, id_))
    except:  # pylint: disable=bare-except
      # need to catch and print exception since it is user visible
      _traceback.print_exc()

  def _gen_js(self, dataframe, id_):
    """Returns javascript for this table."""
    columns = dataframe.columns
    data = dataframe.values

    data_formatters = {}
    header_formatters = {}
    default_formatter = _interactive_table_helper._find_formatter(  # pylint: disable=protected-access
        _DEFAULT_FORMATTERS)

    for i, _ in enumerate(columns):
      data_formatters[i] = default_formatter
      header_formatters[i] = default_formatter

    formatted_data = _interactive_table_helper._format_data(  # pylint: disable=protected-access
        data, _DEFAULT_NONUNICODE_FORMATTER, data_formatters)
    column_types = formatted_data['column_types']

    columns_and_types = []
    for i, (column_type, column) in enumerate(zip(column_types, columns)):
      columns_and_types.append((column_type, str(header_formatters[i](column))))

    return """
      google.colab.output.pauseOutputUntil(createDataTable({{
        data: {data},
        elementId: "{id}",
        columns: {columns},
        rowsPerPage: {num_rows_per_page},
      }}));
    //# sourceURL=table_{id}
    """.format(
        data=formatted_data['data'],
        id=id_,
        columns=_json.dumps(columns_and_types),
        num_rows_per_page=self._num_rows_per_page)


_original_formatters = {}


def enable_dataframe_formatter():
  """Enables DataTable as the default IPython formatter for Pandas DataFrames."""
  key = 'text/html'
  if key not in _original_formatters:
    formatters = _IPython.get_ipython().display_formatter.formatters
    _original_formatters[key] = formatters[key].for_type_by_name(
        'pandas.core.frame', 'DataFrame', DataTable.formatter)


def disable_dataframe_formatter():
  """Restores the original IPython formatter for Pandas DataFrames."""
  key = 'text/html'
  if key in _original_formatters:
    formatters = _IPython.get_ipython().display_formatter.formatters
    # pop() handles the case of original_formatter = None.
    formatters[key].pop('pandas.core.frame.DataFrame')
    formatters[key].for_type_by_name('pandas.core.frame', 'DataFrame',
                                     _original_formatters.pop(key))
