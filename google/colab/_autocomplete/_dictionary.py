"""Provides autocomplete for dict-like structures (e.g. Dataframe)."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import ast

import IPython

import pandas as pd
import six

from google.colab._autocomplete import _inference
from google.colab._autocomplete import _splitter


def _is_of_literal_type(x):
  try:
    ast.literal_eval(repr(x))
    return True
  except:  # pylint: disable=bare-except
    return False


_UNICODE_ESCAPE_MAP = {
    ord(u'"'): u'\\\"',
    ord(u'\''): u'\\\'',
    ord(u'\\'): u'\\\\',
}
for i in range(32):
  _UNICODE_ESCAPE_MAP[i] = six.text_type(chr(i).encode('unicode-escape'))


def _escape_quote(x, quote):
  return x.replace(quote, '\\' + quote)


def _unicode_escape_special(x):
  fmt = u'%s'
  if isinstance(x, six.binary_type):
    x = x.decode('utf8')
  if not isinstance(x, six.text_type):
    raise ValueError('Only str or unicode are supported, got %r ' % (x,))
  return fmt % (x.translate(_UNICODE_ESCAPE_MAP))


def _unicode_repr(x):
  if _is_str_like(x):
    return u"'%s'" % _unicode_escape_special(x)
  else:
    # Have utf-8 character will use u"..." for autocompletion
    return u"u'%s'" % _unicode_escape_special(x)


def _unicode(x):
  """Returns unicode representation of x."""
  if isinstance(x, six.string_types):
    return _unicode_repr(x)
  return u'%r' % (x,)


def _is_str_like(x):
  if isinstance(x, six.binary_type):
    return True
  if isinstance(x, six.text_type) and len(x.encode('utf8')) == len(x):
    return True
  return False


def _item_autocomplete(shell, event):
  """Returns autocomplete options for a dictionary if it is a dictionary.

  Args:
    shell: unused
    event: contains ipython autocomplete event, most importantly it must
    expose text_until_cursor field
  Returns:
    List of possible completions.
  """
  txt = event.text_until_cursor.rstrip()
  lines = txt.rsplit('\n', 1)
  if not lines:
    return
  #  Fast return if the last line doesn't contain '[' or quotes
  if all(s not in lines[-1] for s in '\'"['):
    return

  token = ''
  if not txt.endswith(('[', "['", '["')):
    # See if removing the last token will bring us to the beginning
    # of open bracket.
    token = _splitter.split(txt)
    if not token:
      return
    txt = txt[:-len(token)]
    # If we have something[foo - we can't provide autocompletion
    # we can only do something["foo, or something['foo
    if not txt.endswith(('\'', '"')):
      return

  selector = None
  if txt.endswith('['):
    # For [ we need to provide ['foo'] autocompletion that includes both
    # the bracket and full repr of the key. For autocompletions when
    # user already typed quote, we only need to provide foo'].

    # This is caused
    # by the fact pecularities of ipython processing which requires the
    # autocompletion to match the token it expects (which happens to be empty
    # for ' and being "[" for bracket.

    # Represent this actual unicode string.
    fmt = lambda x: '[' + _unicode(x)
    txt = txt[:-1]
    selector = _is_of_literal_type
  elif txt.endswith(('["', "['")):
    fmt = _unicode_escape_special
    txt = txt[:-2]
    # only give completions on string keys, (note: ignore unicode as well)
    selector = _is_str_like

  if not selector:
    return

  symbol = _splitter.split(txt)
  v = _inference.infer_expression_result(symbol, shell.user_global_ns,
                                         shell.user_ns)

  # we only support keys of length at most 256 and return at most 100 of them
  if isinstance(v, (dict, pd.DataFrame)):
    return [(fmt(k))
            for k in v.keys()
            if selector(k) and len(fmt(k)) < 256 and fmt(k).startswith(token)
           ][0:100]
  return


def enable():
  IPython.get_ipython().set_hook(
      'complete_command', _item_autocomplete, re_key='.*')


# Note: IPython does not provide ability to cleanly remove hooks,  so we
# don't provide one here.
