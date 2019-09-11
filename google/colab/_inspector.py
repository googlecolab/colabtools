# Copyright 2017 Google Inc.
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
"""Colab-specific IPython.oinspect.Inspector and related utilities."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import inspect
import sys
import types

from IPython.core import oinspect
import six
from six.moves import builtins

# We need to reference collections ABCs, which don't have a name in six.moves.
if six.PY2:
  import collections as collections_abc  # pylint: disable=g-import-not-at-top
else:
  import collections.abc as collections_abc  # pylint: disable=g-import-not-at-top

_APPROVED_ITERABLES = {
    dict: ('{', '}'),
    set: ('{', '}'),
    frozenset: ('frozenset({', '})'),
    list: ('[', ']'),
    tuple: ('(', ')'),
}
_ITERABLE_SIZE_THRESHOLD = 5
_MAX_RECURSION_DEPTH = 4
_OBJ_SIZE_LIMIT = 5000
_STRING_ABBREV_LIMIT = 20

# Unhelpful docstrings we avoid surfacing to users.
_BASE_CALL_DOC = types.FunctionType.__call__.__doc__
_BASE_INIT_DOC = object.__init__.__doc__


def _getdoc(obj):
  """Custom wrapper for inspect.getdoc.

  IPython.core.oinspect.getdoc wraps Python's inspect.getdoc to catch exceptions
  and allow for objects with a custom getdoc() method. However, there are two
  problems:
   * inspect.getdoc already catches any exceptions
   * it then calls get_encoding, which calls inspect.getfile, which may call
     repr(obj) (to use in an error string, which oinspect.getdoc throws away).

  We replace this with our own wrapper which still allows for custom getdoc()
  methods, but avoids calling inspect.getfile.

  Args:
    obj: an object to fetch a docstring for

  Returns:
    A docstring or ''.
  """
  if hasattr(obj, 'getdoc'):
    try:
      docstring = obj.getdoc()
    except Exception:  # pylint: disable=broad-except
      pass
    else:
      if isinstance(docstring, six.string_types):
        return docstring

  docstring = inspect.getdoc(obj) or ''
  # In principle, we want to find the file associated with obj, and use that
  # encoding here. However, attempting to find the file may lead to calling
  # repr(obj), so we instead assume UTF8 and replace non-UTF8 characters.
  return six.ensure_text(docstring, errors='backslashreplace')


def _getargspec(obj):
  """Wrapper for oinspect.getargspec."""
  try:
    argspec = oinspect.getargspec(obj)
  except (TypeError, AttributeError):
    return None
  d = dict(argspec._asdict())
  # Work around py2/py3 argspec differences
  # TODO(b/136556288): Remove this.
  if 'varkw' not in d:
    d['varkw'] = d.pop('keywords')
  return d


def _getsource(obj):
  """Safe oinspect.getsource wrapper.

  **NOTE**: this function is may call repr(obj).

  Args:
    obj: object whose source we want to fetch.

  Returns:
    source code or None.
  """
  try:
    return oinspect.getsource(obj)
  except TypeError:
    return None


def _safe_repr(obj, depth=0, visited=None):
  """Return a repr for obj that is guaranteed to avoid expensive computation.

  Colab's UI is aggressive about inspecting objects, and we've discovered that
  in practice, too many objects can have a repr which is expensive to compute.

  To make this work, we whitelist a set of types for which we compute a repr:
   * "large" objects (as determined by sys.getsizeof) get a summary with type
     name and size info
   * builtin types which aren't Iterable are safe, up to size constraints
   * Sized objects with a `.shape` tuple attribute (eg ndarrays and dataframes)
     get a summary with type name and shape
   * list, dict, set, frozenset, and tuple objects we format recursively, up to
     a fixed depth, and up to a fixed length
   * other Iterables get a summary with type name and len
   * all other objects get a summary with type name

  In all cases, we limit:
   * the number of elements we'll format in an iterable
   * the total depth we'll recur
   * the size of any single entry
  Any time we cross one of these thresholds, we use `...` to imply additional
  elements were elided, just as python does when printing circular objects.

  See https://docs.python.org/3/library/collections.abc.html for definitions of
  the various types of collections.

  For more backstory, see b/134847514.

  Args:
    obj: A python object to provide a repr for.
    depth: (optional) The current recursion depth.
    visited: (optional) A set of ids of objects visited so far.

  Returns:
    A (potentially abbreviated) string representation for obj.
  """
  visited = visited or frozenset()

  # First, terminate if we're already too deep in a nested structure..
  if depth > _MAX_RECURSION_DEPTH:
    return '...'

  type_name = type(obj).__name__
  module_name = type(obj).__module__
  size = sys.getsizeof(obj)

  # Next, we want to allow printing for ~all builtin types other than iterables.
  if isinstance(obj, (six.binary_type, six.text_type)):
    if len(obj) > _STRING_ABBREV_LIMIT:
      return repr(obj[:_STRING_ABBREV_LIMIT] + '...')
    return repr(obj)
  # Bound methods will include the full repr of the object they're bound to,
  # which we need to avoid.
  if isinstance(obj, types.MethodType):
    if six.PY3:
      return '{} method'.format(obj.__qualname__)
    else:
      return '{}.{} method'.format(obj.im_class.__name__, obj.__func__.__name__)
  # Matching by module name is ugly; we do this because many types (eg
  # type(None)) don't appear in the dir() of any module in py3.
  if (not isinstance(obj, collections_abc.Iterable) and
      module_name == builtins.__name__):
    if size > _OBJ_SIZE_LIMIT:
      # We don't have any examples of objects that meet this criteria, but we
      # still want to be safe.
      return '<{} object with size {}>'.format(type_name, size)
    return repr(obj)

  # If it wasn't a primitive object, we may need to recur; we see if we've
  # already seen this object, and if not, add its id to the list of visited
  # objects.
  if id(obj) in visited:
    return '...'
  visited = visited.union({id(obj)})

  # Sized & shaped objects get a simple summary.
  if (isinstance(obj, collections_abc.Sized) and
      isinstance(getattr(obj, 'shape', None), tuple)):
    return '{} with shape {}'.format(type_name, obj.shape)

  # We recur on the types whitelisted above; the logic is slightly different for
  # dicts, as they have compound entries.
  if isinstance(obj, dict):
    s = []
    suffix = ''
    for i, (k, v) in enumerate(six.iteritems(obj)):
      if i >= _ITERABLE_SIZE_THRESHOLD:
        s.append('...')
        suffix = ' ({} items total)'.format(len(obj))
        break
      # This is cosmetic: without it, we'd end up with {...: ...}, which is
      # uglier than {...}.
      if depth == _MAX_RECURSION_DEPTH:
        s.append('...')
        break
      s.append(': '.join((
          _safe_repr(k, depth=depth + 1, visited=visited),
          _safe_repr(v, depth=depth + 1, visited=visited),
      )))
    return ''.join(('{', ', '.join(s), '}', suffix))

  if isinstance(obj, tuple(_APPROVED_ITERABLES)):
    # Empty sets and frozensets get special treatment.
    if not obj and isinstance(obj, frozenset):
      return 'frozenset()'
    elif not obj and isinstance(obj, set):
      return 'set()'
    start, end = _APPROVED_ITERABLES[type(obj)]
    s = []
    suffix = ''
    for i, v in enumerate(obj):
      if i >= _ITERABLE_SIZE_THRESHOLD:
        s.append('...')
        suffix = ' ({} items total)'.format(len(obj))
        break
      s.append(_safe_repr(v, depth=depth + 1, visited=visited))
    return ''.join((start, ', '.join(s), end, suffix))

  # Other sized objects get a simple summary.
  if isinstance(obj, collections_abc.Sized):
    try:
      obj_len = len(obj)
      return '{} with {} items'.format(type_name, obj_len)
    except Exception:  # pylint: disable=broad-except
      pass

  # We didn't know what it was; we give up and just give the type name.
  name = getattr(type(obj), '__qualname__', type_name)
  return '{}.{} instance'.format(module_name, name)


class ColabInspector(oinspect.Inspector):
  """Colab-specific object inspector."""

  def info(self, obj, oname='', formatter=None, info=None, detail_level=0):
    """Compute a dict with detailed information about an object.

    This overrides the superclass method for two main purposes:
     * avoid calling str() or repr() on the object
     * use our custom repr

    Args:
      obj: object to inspect.
      oname: (optional) string reference to this object
      formatter: (optional) custom docstring formatter
      info: (optional) previously computed information about obj
      detail_level: (optional) 0 or 1; 1 means "include more detail"

    Returns:
      A dict with information about obj.
    """

    # We want to include the following list of keys for all objects:
    # * name
    # * found
    # * isclass
    # * string_form
    # * type_name
    #
    # For callables, we want to add a subset of:
    # * argspec
    # * call_docstring
    # * definition
    # * docstring
    # * file
    # * init_definition
    # * init_docstring
    # * source_end_line
    # * source_start_line
    #
    # For detail_level 1, we include:
    # * file
    # This can be expensive, as the stdlib mechanisms for looking up the file
    # containing obj may call repr(obj).
    #
    # NOTE: These keys should stay in sync with the corresponding list in our
    # frontend code.
    #
    # We want non-None values for:
    # * isalias
    # * ismagic
    # * namespace
    #
    # TODO(b/138128444): Handle class_docstring and call_def, or determine that
    # we're safe ignoring them.

    obj_type = type(obj)
    out = {
        'name': oname,
        'found': True,
        'is_class': inspect.isclass(obj),
        'string_form': None,
        # Fill in empty values.
        'docstring': None,
        'file': None,
        'isalias': False,
        'ismagic': info.ismagic if info else False,
        'namespace': info.namespace if info else '',
    }
    if detail_level >= self.str_detail_level:
      out['string_form'] = _safe_repr(obj)

    if getattr(info, 'ismagic', False):
      out['type_name'] = 'Magic function'
    else:
      out['type_name'] = obj_type.__name__

    # If the object is callable, we want to compute a docstring and related
    # information. We could exit early, but all the code below is in conditional
    # blocks, so there's no need.
    #
    # We can't simply call into the superclass method, as we need to avoid
    # (transitively) calling inspect.getfile(): this function will end up
    # calling repr() on our object.

    # We want to include a docstring if we don't have source, which happens
    # when:
    # * detail_level == 0, or
    # * detail_level == 1 but we can't find source
    # So we first try dealing with detail_level == 1, and then set
    # the docstring if no source is set.
    if detail_level == 1:
      # This should only ever happen if the user has asked for source (eg via
      # `obj??`), so we're OK with potentially calling repr for now.
      # TODO(b/138128444): Ensure we don't call str() or repr().
      source = _getsource(obj)
      if source is None and hasattr(obj, '__class__'):
        source = _getsource(obj.__class__)
      if source is not None:
        out['source'] = source
    if 'source' not in out:
      formatter = formatter or (lambda x: x)
      docstring = formatter(_getdoc(obj) or '<no docstring>')
      if docstring:
        out['docstring'] = docstring

    if _iscallable(obj):
      filename = oinspect.find_file(obj)
      if filename and (filename.endswith(
          ('.py', '.py3', '.pyc')) or '<ipython-input' in filename):
        out['file'] = filename

      line = oinspect.find_source_lines(obj)
      out['source_start_line'] = line
      # inspect.getsourcelines exposes the length of the source as well, which
      # can be used to highlight the entire code block, but find_source_lines
      # currently does not expose this. For now just highlight the first line.
      out['source_end_line'] = line

    # For objects with an __init__, we set init_definition and init_docstring.
    init = getattr(obj, '__init__', None)
    if init:
      init_docstring = _getdoc(init)
      if init_docstring and init_docstring != _BASE_INIT_DOC:
        out['init_docstring'] = init_docstring
      init_def = self._getdef(init, oname)
      if init_def:
        out['init_definition'] = self.format(init_def)
    # The remaining attributes only apply to classes or callables.
    if inspect.isclass(obj):
      # For classes, the __init__ method is the method invoked on call, but
      # old-style classes may not have an __init__ method.
      if init:
        argspec = _getargspec(init)
        if argspec:
          out['argspec'] = argspec
    elif callable(obj):
      definition = self._getdef(obj, oname)
      if definition:
        out['definition'] = self.format(definition)

      if not oinspect.is_simple_callable(obj):
        call_docstring = _getdoc(obj.__call__)
        if call_docstring and call_docstring != _BASE_CALL_DOC:
          out['call_docstring'] = call_docstring

      out['argspec'] = _getargspec(obj)

    return oinspect.object_info(**out)


def _iscallable(obj):
  """Check if an object is a callable object safe for inspect.find_file."""
  return inspect.ismodule(obj) or inspect.isclass(obj) or inspect.ismethod(
      obj) or inspect.isfunction(obj) or inspect.iscode(obj)
