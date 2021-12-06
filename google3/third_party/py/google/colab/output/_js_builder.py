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
"""Building javascript in python."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import datetime
import functools
import json
import time
import uuid
from google.colab.output import _js
from google.colab.output import _publish


# Different ways of creating javascript
# PERSISTENT: Will result in javascript being saved in the ipynb permanently
# and reexecuting on reload
PERSISTENT = 'persistent'

# EVAL: javascript will be evaled and never saved in ipynb file.
EVAL = 'eval'


class JsException(Exception):  # pylint: disable=g-bad-exception-name
  pass


class Js(object):
  """Base class to execute javascript using python chaining.

  Basic usage is like this:

  alert = Js('alert')

  # equivalent to alert("Hello World") on javascript console
  alert("Hello world")

  jQuery = Js('$') # Assumes jquery is loaded
  jQuery("#my-id").css("background", "green")
  # The result is Js() object, whose properties could be further accessed.
  # For example
  my_dom_el = jQuery("#my-id")  # equivalent to my_dom_el = $("#my-id")
  my_dom_el.css("background", "black) # my_dom_el.css(...)
  # It could also be passed as parameter:
  jQuery(my_dom_el)  # equivalent to $(my_dom_el), etc.

  # Also properties can be accessed normally:
  global = Js()
  global.console.log("hi") # equivalent to console.log("hi")
  global.setTimeout(global.alert, 3000) # setTimeout(alert, 3000)

  If the result of javascript computation is jsonable object one can access
  access its value via eval().

  Supports all basic python types, including L{datetime.datetime} objects.
  """

  def __init__(self, expr=None, mode=PERSISTENT):
    """Constructor.

      win = Js() # Will create an opaque reference to global context
      win.console.log('Test') # will log to javascript console

      js_func = Js('function() { ...}') will create a function that could
      be later called like a regular function.
    Args:
      expr: if provided will create an opaque representatoin
      of this javascript expression and it could be used to directly
      operate on it. If None: will assume a global context.
      mode: how to run javascript, one of (PERSISTENT or EVAL)
    """
    self._attr_map = {}
    self._context = expr
    self._mode = mode
    self._builder = functools.partial(type(self), mode=mode)
    self._run_js = self._get_javascript_runner(mode)

  def _get_javascript_runner(self, mode):
    """Returns an appropriate function that executes the given javascript."""
    if mode == PERSISTENT:
      # Note: want lazy binding, particularly for tests to be able
      # to inject custom handling.
      # pylint: disable=unnecessary-lambda
      return lambda x: _publish.javascript(x)
    elif mode == EVAL:
      # Note: we don't want javascript value on python side
      # unless user specifically requests it using .eval().
      # This allows us to properly chain function and javascript class
      # (since those are not serializable) and eliminates the need to wait
      # for frontend to return.
      return lambda x: _js.eval_js('(()=>{' + x + '})()', ignore_result=True)
    else:
      raise JsException('Invalid mode: %r.' % mode)

  def __repr__(self):
    return 'Js(%s)' % self._context

  def __call__(self, *args, **kwargs):
    """Sends args into javascript call for this context.

    Args:
      *args: list of arguments to pass to a javascript function.
      **kwargs: optional keyword args.  Currently only supports result_name
        to store the result of the call in the named JS variable.  If omitted,
        the result is stored in a window member named after a UUID generated for
        this call.

    Returns:
      A Js object that could be used in arguments or for further chaining.

    Raises:
      JsException:  if this object has no context (e.g. js_global)
      ValueError:   if an unexpected kwargs name is specified
    """
    result_name = kwargs.pop('result_name', None)
    if kwargs:
      raise ValueError('Unexpected kwargs: {}'.format(kwargs))
    return self._get_expr_result(self._call_expr(args), result_name=result_name)

  def _call_expr(self, args):
    """Construct javascript call on current context with args."""
    if self._context is None:
      raise JsException('Cannot call a function with empty context.')
      # Generates argument list without surrounding '[' and ']'
    arg_json = json.dumps(args, cls=_JavascriptEncoder)[1:-1]
    return '%s(%s)' % (self._js_value(), arg_json)

  def _get_expr_result(self, expr, result_name=None):
    result_name = result_name or uuid.uuid1()
    js_result = self._js_value(result_name)
    self._run_js('%s = %s;' % (js_result, expr))
    return self._builder(result_name)

  def _join(self, context, name):
    if context:
      return context + '.' + name
    return name

  def _js_value_as_object(self):
    return self._js_value() or 'window'

  def __getitem__(self, name):
    return self._builder(
        self._js_value_as_object() + '[' + json.dumps(name) + ']')

  def __setitem__(self, name, value):
    """Enables setting properties on javascript object.

    For example:
      output.js_global['foo'] = 'bar' # global variable named foo with value bar
      output.js_global[output.js_global.foo] = 'hi' # 'bar' have value hi.

    Args:
      name: name of the item
      value: the value to set it to - should be json-like data, or JS object
    """
    v = json.dumps(value, cls=_JavascriptEncoder)
    name = json.dumps(name, cls=_JavascriptEncoder)
    self._run_js('%s[%s] = %s;' % (self._js_value_as_object(), name, v))

  def __setattr__(self, name, value):
    """Allows to do variable assignment.

    Note this doesn't allow to assign to variables starting with '_'.
    Args:
      name: The name of the attribute/variable
      value: json-like value, or JS object
    """
    if name.startswith('_'):
      object.__setattr__(self, name, value)
      return
    v = json.dumps(value, cls=_JavascriptEncoder)
    name = json.dumps(name, cls=_JavascriptEncoder)[1:-1]
    result = '%s = %s;' % (self._join(self._js_value(), name), v)
    self._run_js(result)

  def _ipython_display_(self):
    print(repr(self))

  def __getattr__(self, name):
    """Returns a JS object pointing to context.name.

    The result could be used for chaining, as an argument
    or as a function.

    Args:
      name: name of the attribute to look up.
    Returns:
      The named attribute (as a Js object).
    Raises:
      AttributeError: if name is invalid
    """
    # Don't try to evaluate special python functions.
    if name.startswith('__') and name.endswith('__'):
      raise AttributeError('%s not found' % name)
    val = self._attr_map.get(name, None)
    if val is None:
      val = self._builder(self._join(self._js_value(), name))
      self._attr_map[name] = val
    return val

  def _js_value(self, name=None):
    """Return a string representing this object javascript value."""
    if name is None:
      name = self._context
    # Running in global context
    if name is None:
      return ''
    # Context is compound object
    if not isinstance(name, uuid.UUID):
      return name
    # Context is a global variable or artificial uuid
    return 'window["%s"]' % name

  def eval(self):
    """Evals the content on javascript side and returns result.

    Note: if the result of this javascript computation is not
    json serializable (e.g. it is a function or class) this will fail.

    This function does not affect the underlying ipynb.

    Usage example:
       # this is executed on javascript side, x is opaque reference to
       # the result of my_function computation.
       x = output.js_global.my_class.my_function(1, 2, 3)
       # This gets the value to python
       x.eval()

    This works with any javascript mode.
    Returns:
      evaled javascript.
    """
    return _js.eval_js(self._js_value())

  def trait_names(self):
    """IPython expects this function, otherwise getattr() is called ."""
    return []

  # pylint: disable=invalid-name
  def _getAttributeNames(self):
    """Same as trait_names."""
    return self.__dir__()

  def __add__(self, other):
    return self._get_expr_result('%s + %s' % self._arith_args(other))

  def __sub__(self, other):
    return self._get_expr_result('%s - %s' % self._arith_args(other))

  def __mul__(self, other):
    return self._get_expr_result('%s * %s' % self._arith_args(other))

  def __div__(self, other):
    return self._get_expr_result('%s / %s' % self._arith_args(other))

  def __truediv__(self, other):
    return self._get_expr_result('%s / %s' % self._arith_args(other))

  def __mod__(self, other):
    return self._get_expr_result('%s % %s' % self._arith_args(other))

  def __radd__(self, other):
    return self._get_expr_result('%s + %s' % self._arith_args(other)[::-1])

  def __rsub__(self, other):
    return self._get_expr_result('%s - %s' % self._arith_args(other)[::-1])

  def __rmul__(self, other):
    return self._get_expr_result('%s * %s' % self._arith_args(other)[::-1])

  def __rdiv__(self, other):
    return self._get_expr_result('%s / %s' % self._arith_args(other)[::-1])

  def __rmod__(self, other):
    return self._get_expr_result('%s % %s' % self._arith_args(other)[::-1])

  def _arith_args(self, other):
    """Helper for arithmetic support."""
    if self._context is None:
      raise JsException('Cannot do arithmetic on empty context.')
    s = self._js_value()
    o = json.dumps(other, cls=_JavascriptEncoder)
    if not o:
      raise JsException('Cannot do arithmetic on empty operand.')
    return s, o

  def new_object(self, *args):
    """Assuming self describes a type, constructs a new object of that type.

    Example usage:
      THREE = Js('THREE')
      // v now points to new THREE.Vector3(1, 2, 3)
      v = THREE.Vector3.new_object(1, 2, 3)

    Args:
      *args: list of arguments to pass to a javascript constructor.

    Returns:
      A Js object holding the constructed instance.

    Raises:
      JsException: if this object has no context (i.e. not a constructor)
    """
    return self._get_expr_result('new ' + self._call_expr(args))


def _py_datetime_to_js_date(o):
  return Js('new Date(%d)' % (1000 * time.mktime(o.timetuple())))


TYPE_CONVERSION_MAP = {
    datetime.datetime: _py_datetime_to_js_date,
}


class _JavascriptEncoder(json.JSONEncoder):
  """Provides json-esque enconding for Js objects and python standard types.

  Note: while the name suggests JSON, this is not necessarily a json,
  instead it produces valid javascript that looks like json for trivial types,
  but might otherwise contain function calls, new Date() objects etc.
  """

  def __init__(self, *args, **kwargs):
    kwargs['allow_nan'] = False
    json.JSONEncoder.__init__(self, *args, **kwargs)
    self._replacement_map = {}

  def default(self, o):
    if isinstance(o, Js):
      key = uuid.uuid4().hex
      # pylint: disable=protected-access
      self._replacement_map[key] = o._js_value()
      return key
    if hasattr(o, '__javascript__'):
      return Js(o.__javascript__())
    # Get a list of ancestors of kls for new type classes
    # for old-style we don't support inheritance.
    kls = type(o)
    # Note: only new-style classes have mro method.
    bases = kls.mro() if issubclass(kls, object) else [kls]

    # Walk up the inheritance tree (or classes that participate in method
    # resolution),  until we find something in conversion map
    # that's an this class is an instance of.  This way we are guaranteed
    # to go from more specific classes to least specific in resolving
    # which class to use for conversion.
    for each_type in bases:
      if each_type in TYPE_CONVERSION_MAP:
        return TYPE_CONVERSION_MAP[each_type](o)
    return json.JSONEncoder.default(self, o)

  def encode(self, o):
    try:
      result = json.JSONEncoder.encode(self, o)
    except ValueError:
      # If NaN or +/-Infinity are part of the input, we need custom logic,
      # since they're not officially handled as part of JSON. Our solution is
      # the following, involving an extra round-trip through JSON:
      # * first, convert the input to JSON, allowing NaNs,
      # * second, convert *back* to a Python object, but explicitly converting
      #   NaN and +/-Infinity into strings, and
      # * finally, convert our now-NaN-free object to JSON.
      #
      # We do it this way because Python only provides custom hooks for NaN
      # handling at *deserialization* time.
      #
      # Note that we're doing this in the context of a custom JSON serializer,
      # so it's important that we preserve that serializer for the first step,
      # which we do by passing `self.default` as the `default` arg to
      # `json.dumps`.
      nan_free_object = json.loads(
          json.dumps(o, default=self.default),
          parse_constant=lambda constant: constant)
      result = json.dumps(nan_free_object)
    # Why is this correct? Well, it is invalid to have </script> anywhere
    # outside of quotes. (won't be a valid javascript) And it is invalid
    # to have it in quotes, because, browser parser.
    # This fixes the latter issue. It keeps the former invaild.
    result = result.replace('</script>', r'<\/script>')
    for k, v in self._replacement_map.items():
      result = result.replace('"%s"' % (k,), v)
    return result

# global context
js_global = Js()
