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
import warnings as _warnings

from google.colab import _interactive_table_helper
import IPython as _IPython
import six as _six

# pylint: disable=g-import-not-at-top
with _warnings.catch_warnings():
  # Importing via IPython raises a spurious warning, but avoids a version
  # mismatch internally.
  _warnings.simplefilter('ignore')
  from IPython.utils import traitlets as _traitlets

# pylint: enable=g-import-not-at-top


__all__ = [
    'DataTable', 'enable_dataframe_formatter', 'disable_dataframe_formatter',
    'load_ipython_extension', 'unload_ipython_extension'
]

_GVIZ_JS = 'https://ssl.gstatic.com/colaboratory/data_table/a6224c040fa35dcf/data_table.js'

_DATA_TABLE_HELP_URL = 'https://colab.research.google.com/notebooks/data_table.ipynb'

_JAVASCRIPT_MODULE_MIME_TYPE = 'application/vnd.google.colaboratory.module+javascript'

_FAKE_DATAFRAME_COLUMN = '__fake_dataframe_column__'

#  pylint:disable=g-import-not-at-top
#  pylint:disable=g-importing-member
if _six.PY2:
  from cgi import escape as _escape
else:
  from html import escape as _escape
  import pandas as _pd
#  pylint:enable=g-importing-member
#  pylint:enable=g-import-not-at-top


def _force_to_latin1(x):
  return 'nonunicode data: %s...' % _escape(x[:100].decode('latin1'))


_DEFAULT_NONUNICODE_FORMATTER = _force_to_latin1
_DEFAULT_FORMATTERS = {_six.text_type: _six.ensure_str}
_DEFAULT_SUPPRESS_OUTPUT_SCROLLING = True


class DataTable(_IPython.display.DisplayObject):
  """An interactive data table display.

  Attributes:
    include_index: (boolean) whether to include the index in a table by default.
    num_rows_per_page: (int) default number of rows per page.
    max_rows: (int) number of rows beyond which the table will be truncated.
    max_columns: (int) number of columns beyond which the table will be
      truncated.
    min_width: (string) string representing CSS minimum width by default. If
      specified, the table shrink down to the minimum of this value and the
      width needed for the content.
  """
  # Configurable defaults for initialization.
  include_index = True
  num_rows_per_page = 25
  max_rows = 20000
  max_columns = 20
  min_width = None

  @classmethod
  def formatter(cls, dataframe, **kwargs):
    # Don't use data table for hierarchical index or columns.
    if isinstance(dataframe.columns, _pd.MultiIndex):
      return None
    if isinstance(dataframe.index, _pd.MultiIndex):
      return None
    # For large dataframes, fall back to pandas rather than truncating.
    if dataframe.shape[0] > cls.max_rows:
      print(
          ('Warning: total number of rows (%d) exceeds max_rows (%d). '
           'Falling back to pandas display.') % (len(dataframe), cls.max_rows))
      return None
    if dataframe.shape[1] > cls.max_columns:
      print(('Warning: Total number of columns (%d) exceeds max_columns (%d). '
             'Falling back to pandas display.') %
            (len(dataframe.columns), cls.max_columns))
      return None
    return cls(dataframe, **kwargs)._repr_javascript_module_()  # pylint: disable=protected-access

  def __init__(self,
               dataframe,
               include_index=None,
               num_rows_per_page=None,
               max_rows=None,
               max_columns=None,
               min_width=None):
    """Constructor.

    Args:
       dataframe: the dataframe source for the table
       include_index: boolean specifying whether index should be included.
         Defaults to DataTable.include_index
       num_rows_per_page: display that many rows per page initially. Defaults to
         DataTable.num_rows_per_page.
       max_rows: if len(data) exceeds this value a warning will be printed and
         the table truncated. Defaults to DataTable.max_rows.
       max_columns: if len(columns) exceeds this value a warning will be printed
         and truncated. Defaults to DataTable.max_columns.
       min_width: string representing CSS minimum width. If specified, the table
         shrink down to the minimum of this value and the width needed for the
         content.
    """

    def _default(value, default):
      return default if value is None else value

    self._dataframe = dataframe
    self._include_index = _default(include_index, self.include_index)
    self._num_rows_per_page = _default(num_rows_per_page,
                                       self.num_rows_per_page)
    self._max_rows = _default(max_rows, self.max_rows)
    self._max_columns = _default(max_columns, self.max_columns)
    self._min_width = _default(min_width, self.min_width)

    _register_jsmodule_mimetype()

  def _preprocess_dataframe(self):
    if len(self._dataframe.columns) > self._max_columns:
      print(
          ('Warning: Total number of columns (%d) exceeds max_columns (%d)'
           ' limiting to first (%d) columns.') %
          (len(self._dataframe.columns), self._max_columns, self._max_columns))
    if len(self._dataframe) > self._max_rows:
      print(('Warning: total number of rows (%d) exceeds max_rows (%d). '
             'Limiting to first (%d) rows.') %
            (len(self._dataframe), self._max_rows, self._max_rows))
    dataframe = self._dataframe.iloc[:self._max_rows, :self._max_columns]

    if self._include_index or dataframe.shape[1] == 0:
      dataframe = dataframe.reset_index()

    # if the column is uint64 and contains large numbers, convert to object.
    # (see b/140769413 for details)
    for i, dtype in enumerate(dataframe.dtypes):
      if dtype == 'uint64' and (dataframe.iloc[:, i] > 2**63).any():
        dataframe.iloc[:, i] = dataframe.iloc[:, i].astype(object)
    return dataframe

  def _repr_mimebundle_(self, include=None, exclude=None):
    mime_bundle = {'text/html': self._repr_html_()}
    try:
      dataframe = self._preprocess_dataframe()
      mime_bundle[_JAVASCRIPT_MODULE_MIME_TYPE] = self._gen_js(dataframe)
    except:  # pylint: disable=bare-except
      # need to catch and print exception since it is user visible
      _traceback.print_exc()
    return mime_bundle

  def _repr_html_(self):
    return self._dataframe._repr_html_()  # pylint: disable=protected-access

  def _repr_javascript_module_(self):
    try:
      return self._gen_js(self._preprocess_dataframe())
    except:  # pylint: disable=bare-except
      # need to catch and print exception since it is user visible
      _traceback.print_exc()

  def _get_dataframe_values(self, df):
    df.insert(df.shape[1], _FAKE_DATAFRAME_COLUMN, [None] * df.shape[0])
    try:
      values = df.to_numpy(dtype=object)[:, :-1]
    finally:
      del df[_FAKE_DATAFRAME_COLUMN]
    return values

  def _gen_js(self, dataframe):
    """Returns javascript for this table."""
    columns = dataframe.columns
    data = self._get_dataframe_values(dataframe)

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

    column_options = []
    if self._include_index:
      # Collapse index columns to minimum necessary width. We specify 1px but
      # they will auto-expand as necessary.
      column_options = [{
          'width': '1px',
          'className': 'index_column'
      }] * self._dataframe.index.nlevels

    return """
      import "{gviz_url}";

      window.createDataTable({{
        data: {data},
        columns: {columns},
        columnOptions: {column_options},
        rowsPerPage: {num_rows_per_page},
        helpUrl: "{help_url}",
        suppressOutputScrolling: {suppress_output_scrolling},
        minimumWidth: {min_width},
      }});
    """.format(
        gviz_url=_GVIZ_JS,
        data=formatted_data['data'],
        columns=_json.dumps(columns_and_types),
        column_options=_json.dumps(column_options),
        num_rows_per_page=self._num_rows_per_page,
        help_url=_DATA_TABLE_HELP_URL,
        suppress_output_scrolling=_json.dumps(
            _DEFAULT_SUPPRESS_OUTPUT_SCROLLING),
        min_width=('"' + self._min_width +
                   '"') if self._min_width else 'undefined')


class _JavascriptModuleFormatter(_IPython.core.formatters.BaseFormatter):
  format_type = _traitlets.Unicode(_JAVASCRIPT_MODULE_MIME_TYPE)
  print_method = _traitlets.ObjectName('_repr_javascript_module_')


def _register_jsmodule_mimetype():
  """Register _repr_javascript_module_ with the IPython display mechanism."""
  shell = _IPython.get_ipython()
  if not shell:
    return
  display_formatter = shell.display_formatter
  display_formatter.formatters.setdefault(
      _JAVASCRIPT_MODULE_MIME_TYPE,
      _JavascriptModuleFormatter(parent=display_formatter))


_original_formatters = {}


def enable_dataframe_formatter():
  """Enables DataTable as the default IPython formatter for Pandas DataFrames."""
  key = _JAVASCRIPT_MODULE_MIME_TYPE
  if key not in _original_formatters:
    _register_jsmodule_mimetype()
    formatters = _IPython.get_ipython().display_formatter.formatters
    _original_formatters[key] = formatters[key].for_type_by_name(
        'pandas.core.frame', 'DataFrame', DataTable.formatter)


def disable_dataframe_formatter():
  """Restores the original IPython formatter for Pandas DataFrames."""
  key = _JAVASCRIPT_MODULE_MIME_TYPE
  if key in _original_formatters:
    formatters = _IPython.get_ipython().display_formatter.formatters
    # pop() handles the case of original_formatter = None.
    formatters[key].pop('pandas.core.frame.DataFrame')
    formatters[key].for_type_by_name('pandas.core.frame', 'DataFrame',
                                     _original_formatters.pop(key))


def load_ipython_extension(ipython):  # pylint: disable=unused-argument
  """Enable DataTable output for all Pandas dataframes."""
  enable_dataframe_formatter()


def unload_ipython_extension(ipython):  # pylint: disable=unused-argument
  """Disable DataTable output for all Pandas dataframes."""
  disable_dataframe_formatter()
