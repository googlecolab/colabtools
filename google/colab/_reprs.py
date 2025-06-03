"""Rich representations of built-in types."""

import base64
import html
import io
import json
import types
import uuid
import warnings
from google.colab import _inspector
# pytype: disable=import-error
import IPython
from IPython.core import oinspect
import numpy as np
import PIL as pil
# pylint: disable=g-import-not-at-top
# TODO(b/210783561): Keep both imports as we migrate to IPython 7
try:
  with warnings.catch_warnings():
    # Importing via IPython raises a spurious warning, but avoids a version
    # mismatch internally.
    warnings.simplefilter('ignore')
    from IPython.utils import traitlets
except ImportError:
  import traitlets

_original_string_formatters = {}

_original_df_formatters = {}


def _string_intrinsic_repr(_):
  # Add additional data which will let the frontend know this is
  # a string.
  return {'type': 'string'}


_INTRINSIC_MIME_TYPE = 'application/vnd.google.colaboratory.intrinsic+json'


class _IntrinsicTypeFormatter(IPython.core.formatters.BaseFormatter):
  format_type = traitlets.Unicode(_INTRINSIC_MIME_TYPE)
  print_method = traitlets.ObjectName('_repr_intrinsic_type_')
  _return_type = dict


def _register_intrinsic_mimetype():
  """Register _repr_intrinsic_type_ with the IPython display mechanism."""
  shell = IPython.get_ipython()
  if not shell:
    return
  display_formatter = shell.display_formatter
  if display_formatter.formatters.get(_INTRINSIC_MIME_TYPE):
    return

  display_formatter.formatters.setdefault(
      _INTRINSIC_MIME_TYPE, _IntrinsicTypeFormatter(parent=display_formatter)
  )


def enable_string_repr():
  """Enables rich string representation."""
  key = _INTRINSIC_MIME_TYPE
  if key not in _original_string_formatters:
    _register_intrinsic_mimetype()

    shell = IPython.get_ipython()
    if not shell:
      return

    formatters = shell.display_formatter.formatters
    _original_string_formatters[key] = formatters[key].for_type(
        str, _string_intrinsic_repr
    )


def disable_string_repr():
  """Restores the original IPython repr for strings."""

  key = _INTRINSIC_MIME_TYPE
  if key in _original_string_formatters:
    formatters = IPython.get_ipython().display_formatter.formatters
    # pop() handles the case of original_formatter = None.
    formatters[key].pop(str)
    formatters[key].for_type(str, _original_string_formatters.pop(key))


def enable_df_style_formatter():
  """Enable colab's custom styling for pandas Styler objects."""
  key = 'text/html'
  if key in _original_df_formatters:
    return

  shell = IPython.get_ipython()
  if not shell:
    return

  formatters = shell.display_formatter.formatters

  def new_formatter(dataframe):
    return dataframe.set_table_attributes('class="dataframe"')._repr_html_()  # pylint: disable=protected-access

  _original_df_formatters[key] = formatters[key].for_type_by_name(
      'pandas.io.formats.style', 'Styler', new_formatter
  )


def disable_df_style_formatter():
  """Disable colab's custom styling for pandas Styler objects."""
  key = 'text/html'
  if key not in _original_df_formatters:
    return
  formatters = IPython.get_ipython().display_formatter.formatters
  formatters[key].pop('pandas.io.formats.style.Styler')
  formatters[key].for_type_by_name(
      'pandas.io.formats.style', 'Styler', _original_df_formatters.pop(key)
  )

_original_dataframe_metadata_formatters = {}


def enable_dataframe_metadata_repr():
  """Enables dataframe metadata."""
  key = _INTRINSIC_MIME_TYPE
  if key not in _original_dataframe_metadata_formatters:
    _register_intrinsic_mimetype()

    shell = IPython.get_ipython()
    if not shell:
      return

    formatters = shell.display_formatter.formatters
    _original_dataframe_metadata_formatters[key] = formatters[
        key
    ].for_type_by_name(
        'pandas.core.frame', 'DataFrame', _dataframe_intrinsic_repr
    )


def disable_dataframe_metadata_repr():
  """Enables dataframe metadata."""

  key = _INTRINSIC_MIME_TYPE
  if key in _original_dataframe_metadata_formatters:
    formatters = IPython.get_ipython().display_formatter.formatters
    # pop() handles the case of original_formatter = None.
    formatters[key].pop('pandas.core.frame.DataFrame')
    formatters[key].for_type_by_name(
        'pandas.core.frame',
        'DataFrame',
        _original_dataframe_metadata_formatters.pop(key),
    )


def _dataframe_intrinsic_repr(dataframe):
  """Annotates a dataframe repr with some metadata about the object."""
  result = {
      'type': 'dataframe',
  }
  varname = ''
  if ip := IPython.get_ipython():
    namespace = ip.user_ns
    found = False
    for varname, var in namespace.items():
      if dataframe is var and not varname.startswith('_'):
        result['variable_name'] = varname
        found = True
        break
    if not found:
      last_line = ip.user_ns['In'][-1].strip().rpartition('\n')[-1]
      varname, dot, operator = last_line.partition('.')
      if varname.isidentifier() and dot and operator.startswith('head('):
        import pandas as pd

        possible_df = ip.user_ns.get(varname)
        if isinstance(possible_df, pd.DataFrame):
          result['variable_name'] = varname
          dataframe = possible_df

  try:
    if summary := _summarize_dataframe(dataframe, varname):
      result['summary'] = summary
  except Exception as e:  # pylint: disable=broad-except
    result['repr_error'] = str(e)

  return result


_MAX_DATAFRAME_ROWS = 100000
_MAX_DATAFRAME_COLS = 20


def _summarize_dataframe(df, variable_name):
  """Summarizes a dataframe."""
  from google.colab import _dataframe_summarizer

  if len(df) > _MAX_DATAFRAME_ROWS or len(df.columns) > _MAX_DATAFRAME_COLS:
    return None

  summary = _dataframe_summarizer.summarize_dataframe(df, variable_name)
  return json.dumps(
      summary,
      indent=2,
      # This is used for serializing any types unknown to Python's json
      # serialization.
      default=str,
      # NaN's are non-standard JSON and cannot be decoded by clients.
      allow_nan=False,
  )


def enable_pandas_series_repr():
  """Enables pandas Series representation in HTML display formatting."""
  shell = IPython.get_ipython()
  if not shell:
    return

  def _pandas_series_to_html(series):
    """Renders a pandas Series as a DataFrame HTML table with a dtype label."""
    series_as_table_html = series.to_frame()._repr_html_()  # pylint: disable=protected-access
    series_as_table_html += f'<br><label><b>dtype:</b> {series.dtype}</label>'
    return series_as_table_html

  html_formatter = shell.display_formatter.formatters['text/html']
  html_formatter.for_type_by_name(
      'pandas.core.series', 'Series', _pandas_series_to_html
  )


def disable_pandas_series_repr():
  """Disables pandas Series representation in HTML display formatting."""
  shell = IPython.get_ipython()
  if not shell:
    return

  html_formatter = shell.display_formatter.formatters['text/html']
  html_formatter.pop('pandas.core.series.Series', default=None)


def _fullname(obj):
  module = obj.__module__
  if module == 'builtins' or module == '__main__':
    return obj.__qualname__
  return module + '.' + obj.__qualname__


def _function_repr(obj):
  """Renders a function repr."""
  try:
    name = _fullname(obj)

    decl = _inspector.get_source_definition(obj)
    init = getattr(obj, '__init__', None)
    if not decl and init:
      decl = _inspector.get_source_definition(init)
    if not decl:
      return

    result = (
        '<div style="max-width:800px; border: 1px solid'
        ' var(--colab-border-color);">'
    )
    result += """<style>
      pre.function-repr-contents {
        overflow-x: auto;
        padding: 8px 12px;
        max-height: 500px;
      }

      pre.function-repr-contents.function-repr-contents-collapsed {
        cursor: pointer;
        max-height: 100px;
      }
    </style>
    """

    result += (
        """<pre style="white-space: initial; background:
         var(--colab-secondary-surface-color); padding: 8px 12px;
         border-bottom: 1px solid var(--colab-border-color);">"""
        + f'<b>{html.escape(name)}</b><br/>'
        + html.escape(decl)
        + '</pre>'
    )

    filename = oinspect.find_file(obj) or ''
    docs = _inspector.getdoc(obj) or '<no docstring>'
    result += (
        '<pre class="function-repr-contents function-repr-contents-collapsed"'
        ' style="">'
    )
    result += (
        '<a class="filepath" style="display:none"'
        f' href="#">{html.escape(filename)}</a>'
    )

    result += html.escape(docs) + '</pre>'
    if filename and '<ipython-input' not in filename:
      line = oinspect.find_source_lines(obj)
      result += f"""
      <script>
      if (google.colab.kernel.accessAllowed && google.colab.files && google.colab.files.view) {{
        for (const element of document.querySelectorAll('.filepath')) {{
          element.style.display = 'block'
          element.onclick = (event) => {{
            event.preventDefault();
            event.stopPropagation();
            google.colab.files.view(element.textContent, {line});
          }};
        }}
      }}
      for (const element of document.querySelectorAll('.function-repr-contents')) {{
        element.onclick = (event) => {{
          event.preventDefault();
          event.stopPropagation();
          element.classList.toggle('function-repr-contents-collapsed');
        }};
      }}
      </script>
      """
    result += '</div>'
    return result
  except Exception:  # pylint: disable=broad-except
    return None


def enable_function_repr():
  """Enables function and class reprs."""

  shell = IPython.get_ipython()
  if not shell:
    return

  html_formatter = shell.display_formatter.formatters['text/html']
  html_formatter.for_type(types.FunctionType, _function_repr)
  html_formatter.for_type(types.MethodType, _function_repr)
  html_formatter.for_type(type, _function_repr)


def disable_function_repr():
  """Disables function and class HTML repr."""

  shell = IPython.get_ipython()
  if not shell:
    return

  html_formatter = shell.display_formatter.formatters['text/html']
  html_formatter.pop(types.FunctionType)
  html_formatter.pop(type)


_MIN_IMG_DIMENSIONS = 10
_MAX_IMG_DIMENSION = 1000


def _image_repr(ndarray: np.ndarray):
  """Renders an ndarray as HTML if it is image-like."""
  try:
    if not np.issubdtype(ndarray.dtype, np.uint8):
      return

    if not (ndarray.ndim == 2 or (ndarray.ndim == 3 and ndarray.shape[2] == 3)):
      return

    if (
        ndarray.shape[0] < _MIN_IMG_DIMENSIONS
        or ndarray.shape[0] > _MAX_IMG_DIMENSION
    ):
      return

    if (
        ndarray.shape[1] < _MIN_IMG_DIMENSIONS
        or ndarray.shape[1] > _MAX_IMG_DIMENSION
    ):
      return

    img = pil.Image.fromarray(ndarray)
    buffered = io.BytesIO()
    img.save(buffered, format='PNG')
    encoded = base64.b64encode(buffered.getvalue()).decode('utf-8')
    uri = 'data:image/png;base64,' + encoded

    result = """<style>
      .ndarray_repr .ndarray_raw_data {
        display: none;
      }
      .ndarray_repr.show_array .ndarray_raw_data {
        display: block;
      }
      .ndarray_repr.show_array .ndarray_image_preview {
        display: none;
      }
      </style>
      """
    html_id = f'id-{uuid.uuid4()}'
    result += f'<div id="{html_id}" class="ndarray_repr">'

    result += (
        f'<pre>ndarray {ndarray.shape} <button style="padding: 0 2px;">show'
        ' data</button></pre>'
    )
    result += f'<img src="{uri}" class="ndarray_image_preview" />'

    result += (
        f'<pre class="ndarray_raw_data">{html.escape(ndarray.__repr__())}</pre>'
    )
    result += '</div>'

    result += f"""<script>
      (() => {{
      const titles = ['show data', 'hide data'];
      let index = 0
      document.querySelector('#{html_id} button').onclick = (e) => {{
        document.querySelector('#{html_id}').classList.toggle('show_array');
        index = (++index) % 2;
        document.querySelector('#{html_id} button').textContent = titles[index];
        e.preventDefault();
        e.stopPropagation();
      }}
      }})();
    </script>"""
    return result
  except Exception:  # pylint: disable=broad-except
    return None


def enable_ndarray_repr():
  """Enables ndarray HTML repr."""
  shell = IPython.get_ipython()
  if not shell:
    return
  html_formatter = shell.display_formatter.formatters['text/html']
  html_formatter.for_type(np.ndarray, _image_repr)


def disable_ndarray_repr():
  """Disables ndarray HTML repr."""

  shell = IPython.get_ipython()
  if not shell:
    return

  html_formatter = shell.display_formatter.formatters['text/html']
  html_formatter.pop(np.ndarray)
