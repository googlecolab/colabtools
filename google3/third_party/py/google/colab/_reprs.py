"""Rich representations of built-in types."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import warnings
# pytype: disable=import-error
import IPython
# pylint: disable=g-import-not-at-top
with warnings.catch_warnings():
  # Importing via IPython raises a spurious warning, but avoids a version
  # mismatch internally.
  warnings.simplefilter('ignore')
  from IPython.utils import traitlets

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
      _INTRINSIC_MIME_TYPE, _IntrinsicTypeFormatter(parent=display_formatter))


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
        str, _string_intrinsic_repr)


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
      'pandas.io.formats.style', 'Styler', new_formatter)


def disable_df_style_formatter():
  """Disable colab's custom styling for pandas Styler objects."""
  key = 'text/html'
  if key not in _original_df_formatters:
    return
  formatters = IPython.get_ipython().display_formatter.formatters
  formatters[key].pop('pandas.io.formats.style.Styler')
  formatters[key].for_type_by_name('pandas.io.formats.style', 'Styler',
                                   _original_df_formatters.pop(key))
