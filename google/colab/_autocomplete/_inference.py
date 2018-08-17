"""Provides support for type inference during autocompletion.

Provides decorators, that can be used to enable autocomplete on results
of function calls.  See below for annotations that you can use to mark
your functions safe to eval, and/or return specific types, etc.
"""
import ast
import functools
import inspect
import math
import tempfile
import types


class _FuncTransformer(ast.NodeTransformer):
  """Replaces all function calls x(y) with _infertype(x, y)."""

  # Overrides function of ast.NodeTransformer
  # pylint: disable=invalid-name
  def visit_Call(self, node):
    """Overrides calls in ast."""
    func = node.func
    node.func = ast.Name(
        id='_autocomplete_infertype',
        lineno=node.lineno,
        col_offset=node.col_offset,
        ctx=node.func.ctx)
    node.args[:0] = [func]
    return self.generic_visit(node)


_BuiltinDescriptorType = type(str.split)

# Maps type(f) to unique descriptor describing given function.
# we want all foo.bar() to map to the same function for all foo of the same
# type.
_PROTOTYPES = {
    # buitlin bound instance method like ''.str, also matches global
    # functions, in which case f.__self__ is None.
    types.BuiltinMethodType:
        lambda f: (type(f.__self__), f.__name__),

    # either unbound or bound method like foo.bar(), we don't need im_class
    # since im_func is actually unique. This is contrast with builtins where
    # we can only get their string name.
    types.MethodType:
        lambda f: (f.im_func),

    # str.split()
    _BuiltinDescriptorType:
        lambda f: (f.__objclass__, f.__name__),

    # Lambda and regular functions return self for indexing
    types.LambdaType: (lambda f: f),
    types.FunctionType: (lambda f: f),
}

_type_map = {}
_safe_to_eval_classes = set()

# Contains the last exception error during autocompletion
_last_autocompletion_error = None


def _get_prototype(func):
  """Returns a prototype of a function.

  This function returns essentially a normalized version of the function that
  is independent of attached instance and only depends on the actual code
  that will be executed when this function is called.

  Args:
    func: a callable

  Returns:
    A signature that is the same for all functions that are essentially the
    same.

  """
  t = type(func)
  if t in _PROTOTYPES:
    return _PROTOTYPES[t](func)

  # Note: if we are here, we know that func is actually not a function
  # but it could be either a class (e.g. this is a constructor call)
  # or an instance. (E.g. this is an instance w/defined __call__)
  #
  # If object has __call__ and not a class (e.g. instance),
  # it is indexed by class/__call__
  if callable(func) and not inspect.isclass(func):
    return type(func), func.__call__

  return func


def _infertype(*args, **kwargs):
  func = args[0]
  prototype = _get_prototype(func)
  inferrer = _type_map.get(prototype, None)
  if inferrer:
    return inferrer(func, *args[1:], **kwargs)
  else:
    return None


def safe_to_eval(func):
  """Indicates that 'func' is safe to eval during autocomplete.

  Can be used as annotation on arbitrary functions, e.g.

      @autocomplete.safe_to_eval
      def pure_func(x, y):
        return x + y

  Args:
    func: function

  Returns:
    func.

  """
  _type_map[_get_prototype(func)] = (
      lambda f, *args, **kwargs: f(*args, **kwargs))
  return func


def is_class_safe_to_eval(t):
  """Returns whether type t was previously marked as safe_to_eval."""
  return t in _safe_to_eval_classes


def _annotate_with_type_inferrer(type_inferrer, func):
  """Registers type_inferrer to be used to infer the result type of func.

  See use_inferrer for public API.

  Args:
     type_inferrer: function that takes as an argument a func and all arguments
     func: function that will be applied to.
  Returns:
    func
  """
  _type_map[_get_prototype(func)] = type_inferrer
  return func


def use_inferrer(inferrer):
  """Allows to annotate given function with return type inferrer.

  Example:
  def inferrer(f, arg):
    '''Does result inference for complex_function depending on arg'''
    return '' if arg is None else arg

  @use_inferrer(inferrer)
  def complex_function(arg):
    ... do something complex

  For the purposes of autocompletion, complex_function(arg) will be assumed
  to have type 'string' if arg is None, and arg, if it is not.

  This is the most generic way of annotating a function, it can use
  both the function and the arguments that were passed in to compute what
  the resulting type/object should be.

  Args:
    inferrer: is a function that takes function as a first argument
    followed by args/kwargs and returns the desired mock return instance that
    will be used for autocompletion

  Returns:
    a decorator that can be applied to any function.
  """
  return functools.partial(_annotate_with_type_inferrer, inferrer)


def returns_instance(instance):
  """Indicates that given function always returns instance.

  Use as annotation e.g.

  @returns_instance('')
  def this_method_returns_string(): LoadStringFromBigtable(...)

  Args:
    instance: instance to return

  Returns:
    Annotation function.
  """
  return use_inferrer(lambda f, *argv, **kwargs: instance)


def returns_arg(arg):
  """Annotates function to return argument for the purposes of autocomplete."""
  return use_inferrer(lambda f, *argv, **kwargs: argv[arg])


def returns_kwarg(arg):
  """Annotates function to return kwarg for the purposes of autocomplete."""
  return use_inferrer(lambda f, *argv, **kwargs: kwargs[arg])


def infer_expression_result(expr, global_ns, local_ns):
  """Returns the result of the expression, or None if not successful.

  Functions are not evaluated and instead infertype is used.

  Args:
    expr: string containing expression
    global_ns: global namespace
    local_ns: local namespace

  Returns:
    the result or None
  """
  tree = ast.parse(expr, mode='eval')
  _FuncTransformer().visit(tree)
  local_ns = dict(local_ns) if local_ns else {}
  local_ns['_autocomplete_infertype'] = _infertype

  try:
    return eval(  # pylint: disable=eval-used
        compile(tree, '<string>', 'eval'), global_ns, local_ns)
  except Exception as e:  # pylint: disable=broad-except
    global _last_autocompletion_error
    _last_autocompletion_error = e

    return None


def mark_class_safe_to_eval(m):
  _safe_to_eval_classes.add(m)
  for each in dir(m):
    if each.startswith('_'):
      continue
    safe_to_eval(getattr(m, each))


def annotate_builtins():
  mark_class_safe_to_eval(str)
  mark_class_safe_to_eval(unicode)
  mark_class_safe_to_eval(math)
  returns_instance(tempfile.mktemp())(open)
