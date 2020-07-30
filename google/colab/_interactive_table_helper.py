# Copyright 2019 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Helper for constructing interactive tables."""

from __future__ import absolute_import as _
from __future__ import division as _
from __future__ import print_function as _

import json as _json
import numbers as _numbers

import six as _six

#  pylint:disable=g-import-not-at-top
#  pylint:disable=g-importing-member
if _six.PY2:
  from cgi import escape as _escape
else:
  import html as _html
  import pandas as _pd

  # html.escape has replaced deprecated cgi.escape, but has different default
  # arguments.
  def _escape(s):
    return _html.escape(s, quote=None)


#  pylint:enable=g-importing-member
#  pylint:enable=g-import-not-at-top


class _CellValue(dict):
  """Encodes cell value dictionary that should be passed to javascript side."""


def _is_numpy_type(x):
  """Returns true if the value is a numpy type."""
  return 'numpy' in str(type(x))


def _find_formatter(formatters):
  """Returns a formatter that takes x, and applies formatter based on types.

  Args:
    formatters: map from type to formatter

  Returns:
    function: x -> displayable output
  """

  def formatter(x):
    for type_, formatter_for_type in formatters.items():
      if isinstance(x, type_):
        return formatter_for_type(x)
    return x

  return formatter


_NP_INT_TYPES = ('int32', 'int64', 'int8', 'int16', 'uint32', 'uint64', 'uint8',
                 'uint16')


def _process_custom_formatters(formatters, columns):
  """Re-keys a dict of custom formatters to only use column indices.

  Args:
    formatters: A dict of formatters, keyed by column index or name.
    columns: The list of columns names.

  Returns:
    A dict of formatters keyed only by column index.
  """
  if not formatters:
    return {}

  # Check that all keys provided are valid column names or indices.
  # Warn if something doesn't check out.
  column_set = set(columns)
  for col in formatters:
    if isinstance(col, int) and col >= len(columns):
      print(('Warning: Custom formatter column index %d exceeds total number '
             'of columns (%d)') % (col, len(columns)))

    if not isinstance(col, int) and col not in column_set:
      print(('Warning: Custom formatter column name %s not present in column '
             'list') % col)

  # Separate out the custom formatters that use indices.
  output_formatters = {
      k: v for k, v in formatters.items() if isinstance(k, int)
  }

  for i, name in enumerate(columns):
    # Attempt to find a formatter based on column name.
    if name in formatters:
      if i in output_formatters:
        print(('Warning: Custom formatter for column index %d present, '
               'ignoring formatter for column name %s') % (i, name))
      else:
        output_formatters[i] = formatters[name]

  return output_formatters


def _fix_large_ints(x):
  # javascript stores all numbers as floats, so large integers must be
  # represented as strings.
  if isinstance(x, _six.integer_types) and abs(x) > 2**52:
    return str(x)
  elif isinstance(x, list):
    return [_fix_large_ints(e) for e in x]
  return x


def _to_js(x,
           default_nonunicode_formatter,
           formatter=None,
           as_string=False,
           html_encode=False):
  """Formats given x into js-parseable structure.

  Args:
    x: describes the data
    default_nonunicode_formatter: The default formatter to use for non-Unicode.
    formatter: function-like object that takes x and returns html string.
    as_string: force the value to be a string in the JSON.
    html_encode: escape HTML characters in strings.

  Returns:
    string - the javascript representation
  """
  if formatter is not None:
    x = formatter(x)
  # Making the output a list, causes datatable interpret its elements
  # as html, rather than text.
  if hasattr(x, '__html__'):
    x = x.__html__()
  elif hasattr(x, '_repr_html_'):
    x = x._repr_html_()  # pylint: disable=protected-access

  # These converters are meant to produce reasonable values
  # but for anything customizables users should just create per-type
  # converters in interactive_table.DEFAULT_FORMATTERS
  if _is_numpy_type(x) and hasattr(x, 'dtype'):
    if x.dtype.kind == 'M':
      x = str(_pd.to_datetime(x))
    elif x.shape:
      # Convert lists into their string representations
      x = str(x)
    elif x.dtype.kind == 'b':
      x = bool(x)
    elif type(x).__name__.startswith('float'):
      if hasattr(x, 'is_integer') and x.is_integer():
        x = int(x)
      else:
        x = float(x)
    elif type(x).__name__ in _NP_INT_TYPES:
      x = int(x)

  x = _fix_large_ints(x)

  represent_as_string = str
  if html_encode:
    represent_as_string = lambda x: _escape(str(x))

  if isinstance(x, dict) and not isinstance(x, _CellValue):
    # dictionaries need to be converted to string, if not they will be passed
    # verbatim to json and they will be shown as Object on javascript side.
    # Note: this keeps x as json-able object, so it will ignore default=
    # encode below and we don't do double encoding.
    x = represent_as_string(x)

  if isinstance(x, list):
    # If this is a list of dictionaries, we need to convert each dict to
    # a string.
    if all(
        (isinstance(el, dict) and not isinstance(el, _CellValue) for el in x)):
      x = [represent_as_string(elem) for elem in x]
    else:
      x = [_fix_large_ints(item) for item in x]

  # Ensure that we're returning JSON of a string value.
  double_encode_json = as_string and not isinstance(x, _six.string_types)

  try:
    result = _json.dumps(x, default=represent_as_string)
  except UnicodeDecodeError:
    if isinstance(x, _six.string_types):
      result = _json.dumps(default_nonunicode_formatter(x))
    else:
      result = _json.dumps([
          _to_js(el, default_nonunicode_formatter, html_encode=html_encode)
          for el in x
      ])
  result = result.replace('</', '<\\/')
  if double_encode_json:
    result = _json.dumps(result)
  return result


def _to_js_matrix(matrix, default_nonunicode_formatter, custom_formatters,
                  max_data_size):
  """Creates a two dimensional javascript compatible matrix.

  Args:
      matrix: is any iterator-of-iterator matrix. Currently the individual type
        should be numbers of strings.
      default_nonunicode_formatter: The default formatter to use for
        non-Unicode.
      custom_formatters: a map that provides custom formatters for some or all
        columns.
      max_data_size: maximum size allowed, if exceeds, the remaining rows will
        be dropped

  Returns:
     javascript representation.
  """

  def _row_to_js(row):
    for i, el in enumerate(row):
      yield _to_js(
          el,
          default_nonunicode_formatter,
          custom_formatters.get(i, None),
          html_encode=True)

  values = [','.join(_row_to_js(row)) for row in matrix]
  total = 0
  discarded = 0
  i = len(values)
  for i, each in enumerate(values):
    total += len(each) + 10
    if total > max_data_size:
      discarded = len(values) - i
      values = values[:i]
      break
  if discarded:
    print(('The table data exceeds the limit %d. Will discard last %d rows ' %
           (max_data_size, discarded)))
  return '[[%s]]' % ('],\n ['.join(values))


def _trim_columns(columns, max_columns):
  """Prints a warning and returns trimmed columns if necessary."""
  if len(columns) <= max_columns:
    return columns
  print(('Warning: Total number of columns (%d) exceeds max_columns (%d)'
         ' limiting to first max_columns ') % (len(columns), max_columns))
  return columns[:max_columns]


def _trim_data(data, max_rows, max_columns=None):
  """Prints a warning and returns trimmed data if necessary."""

  # If the number of columns per row exceeds the max, we need to trim each row.
  if max_columns is not None and len(data) and len(data[0]) > max_columns:
    for i, _ in enumerate(data):
      data[i] = data[i][:max_columns]

  if len(data) <= max_rows:
    return data
  print(('Warning: total number of rows (%d) exceeds max_rows (%d). '
         'Limiting to first max_rows.') % (len(data), max_rows))
  return data[:max_rows]


_NUMBER_TYPES = ('int', 'uint', 'long', 'float')
_ALLOWED_TYPES = _NUMBER_TYPES + ('string', 'NoneType')


def _determine_column_type(data_types):
  """Given a set of Python column types, returns either 'number' or 'string'."""
  # Allow None which will be converted to NaN.
  if all(
      issubclass(t, (_numbers.Number, type(None))) and not issubclass(t, bool)
      for t in data_types):
    return 'number'
  return 'string'


def _get_value(cell):
  if isinstance(cell, _CellValue):
    return cell['v']
  else:
    return cell


def _get_formatted(cell):
  if isinstance(cell, _CellValue):
    return cell['f']
  else:
    return cell


def _get_column_type(data, column_index):
  """Returns the best-guess JS type for the column in the data."""
  data_types = set()
  for row in data:
    cell = row[column_index]
    t = type(_get_value(cell))
    is_known_type = (
        cell is None or issubclass(t, _numbers.Number) or
        issubclass(t, _six.string_types))
    if not is_known_type:
      t = str
    data_types.add(t)
  return _determine_column_type(data_types)


def _num_columns(data):
  """Find the number of columns in a raw data source.

  Args:
    data: 2D numpy array, 1D record array, or list of lists representing the
      contents of the source dataframe.

  Returns:
    num_columns: number of columns in the data.
  """
  if hasattr(data, 'shape'):  # True for numpy arrays
    if data.ndim == 1:
      # 1D record array; number of columns is length of compound dtype.
      return len(data.dtype)
    elif data.ndim == 2:
      # 2D array of values: number of columns is in the shape.
      return data.shape[1]
    else:
      raise ValueError('data expected to be a 2D array or 1D record array.')
  elif data:
    # List of lists: first entry is first row.
    return len(data[0])
  else:
    # Empty list has zero columns
    return 0


def _format_data(data, default_formatter, custom_formatters, html_encode=False):
  """Formats the given data and determines column types."""
  column_types = [_get_column_type(data, i) for i in range(_num_columns(data))]
  formatted_values = []
  for row in data:
    formatted_row = []
    for column_index, cell in enumerate(row):
      custom_formatter = custom_formatters.get(column_index, None)
      formatted_value = cell
      if custom_formatter:
        formatted_value = custom_formatter(formatted_value)
      column_type = column_types[column_index]
      if column_type != 'number' or not custom_formatter:
        formatted_row.append(
            _to_js(formatted_value, default_formatter, html_encode=html_encode))
      else:
        raw_value = _to_js(
            _get_value(cell), default_formatter, html_encode=html_encode)
        formatted_value = _to_js(
            _get_formatted(formatted_value),
            default_formatter,
            as_string=True,
            html_encode=html_encode)
        formatted_row.append("""{
            'v': %s,
            'f': %s,
        }""" % (raw_value, formatted_value))

    formatted_values.append(',\n'.join(formatted_row))

  if formatted_values:
    formatted_data = '[[%s]]' % ('],\n ['.join(formatted_values))
  else:
    formatted_data = '[]'

  return {'column_types': column_types, 'data': formatted_data}
