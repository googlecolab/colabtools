"""Customization of debugpy representation of variables."""

import collections.abc as collections_abc

# Notes on debugpy's reprs-
# Variables are serialized starting in
# pydevd/_pydevd_bundle/pydevd_suspended_frames.py
# Each frame of a paused thread will have a _FrameVariable which is used to
# represent a frame as a variable with a collection of child variables, which
# are all _ObjectVariables.
# _ObjectVariables representing complex types will have _ObjectVariables as
# children, unless they have no children at all.


# Fork of
# debugpy/third_party/pydevd/_pydevd_bundle/pydevd_suspended_frames.py
# to add shape to custom types.
def _get_var_data(self, fmt=None):
  """Gets the debug adapter protocol variable representation.

  Args:
    self: The AbstractVariable
    fmt: Optional formatting params from the request.

  Returns:
    Dict representing the debug adapter protocol variable.
  """

  var_data = _original_get_var_data(self, fmt)
  shape = get_shape(self.value)
  if shape:
    presentation_hint = var_data.get('presentationHint', {})
    presentation_hint['shape'] = shape
    var_data['presentationHint'] = presentation_hint

  return var_data


_CONTAINER_TYPES = (set, frozenset, list, tuple)


# TODO(b/141957613): Share this with _inspector.py when migrating to
# third_party/py/google/colab.
def get_shape(obj):
  """Gets the shape descriptor for an arbitrary object.

  Args:
    obj: The object to inspect.

  Returns:
    A string representing the shape or none.
  """
  if isinstance(obj, collections_abc.Sized):
    shape = getattr(obj, 'shape', None)
    if (isinstance(shape, tuple) or
        hasattr(shape, '__module__') and isinstance(shape.__module__, str) and
        'tensorflow.' in shape.__module__):
      return str(shape)

  if isinstance(obj, _CONTAINER_TYPES):
    return '{} items'.format(len(obj)) if len(obj) != 1 else '1 item'
  if isinstance(obj, str):
    return '{} chars'.format(len(obj)) if len(obj) != 1 else '1 char'
  if isinstance(obj, bytes):
    return '{} bytes'.format(len(obj)) if len(obj) != 1 else '1 byte'
  return None


_original_get_var_data = None


def patch_debugpy_repr():
  """Patches the debugpy default repr for additional customization."""
  global _original_get_var_data
  if not _original_get_var_data:
    try:
      # pytype: disable=import-error
      from _pydevd_bundle.pydevd_suspended_frames import _AbstractVariable  # pylint: disable=g-import-not-at-top
      # pytype: enable=import-error
      _original_get_var_data = _AbstractVariable.get_var_data
      _AbstractVariable.get_var_data = _get_var_data
    except ModuleNotFoundError:
      # _pydev_bundle may be vendored into a different location.
      pass
    try:
      # pytype: disable=import-error
      from pydevd._pydevd_bundle.pydevd_suspended_frames import _AbstractVariable  # pylint: disable=g-import-not-at-top
      # pytype: enable=import-error
      _original_get_var_data = _AbstractVariable.get_var_data
      _AbstractVariable.get_var_data = _get_var_data
    except ModuleNotFoundError:
      # _pydev_bundle may be vendored into a different location.
      pass
