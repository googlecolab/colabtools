"""Contains drop in replacement for IPython.CompletionSplitter class."""
import re
import tokenize

# List of positional params as they arrive from the callback
_TOKEN_TYPE = 0
_TOKEN = 1
_TOKEN_START = 2
_TOKEN_END = 3

_brackets = {']': '[', ')': '(', '.': '.'}


def _quittable(context, token_type, token, *unused_args):
  """Returns true if given token might be the end of the completion token."""

  if token in _brackets:
    return False
  if (token_type in {tokenize.NAME, tokenize.STRING, tokenize.NUMBER} and
      context.maybe_followed_by_name):
    return False

  return True


def _push_token(context, unused_token_type, token, *unused_args):
  """Pushes token into a stack as needed."""
  if token in _brackets.values():
    context.maybe_followed_by_name = True
  else:
    context.maybe_followed_by_name = False

  stack = context.stack
  # Remove the previous period first, since it is just there to ensure
  # that we get the hold on to next token
  if stack and stack[-1] == '.':
    stack.pop()

  if token in _brackets:
    stack.append(_brackets[token])

  elif token == '.':
    stack.append('.')
  elif not stack:
    return
  elif stack[-1] == token:
    stack.pop()


class _Context(object):
  """Describes current parsing context as we parse from right to left."""

  def __init__(self):
    self.stack = []
    self.maybe_followed_by_name = False


def _find_expression_start(tokens):
  """Finds the start of the expression that needs autocompletion.

  Args:
    tokens: list of tokens, where each token is 5-tuple as arrived from
     'tokenize'
  Returns:
    index of the first token that should be included in completion.
  """
  if not tokens:
    return 0
  # Last token is eof, ignore
  i = len(tokens) - 1
  while tokens[i][_TOKEN_TYPE] in {tokenize.ENDMARKER, tokenize.DEDENT}:
    i -= 1
  context = _Context()
  context.maybe_followed_by_name = True
  while i >= 0 and (context.stack or not _quittable(context, *tokens[i])):
    _push_token(context, *tokens[i])
    i -= 1

  return i + 1


def _last_real_token(tokens):
  i = len(tokens) - 1
  while i >= 0 and tokens[i][_TOKEN_TYPE] == tokenize.ENDMARKER:
    i -= 1
  if i < 0:
    return ''
  return tokens[i][_TOKEN]


def split(s):
  """Splits one last token that needs to be autocompleted."""
  # Treat magics specially, since they don't follow python syntax
  # and require '%%' symbols to be preserved
  magic_match = re.search(r'%%?\w+$', s)
  if magic_match:
    return magic_match.group(0)

  s2 = s.rstrip()
  if s != s2:
    # If there is whitespace at the end of the string
    # the completion token is empty
    return ''
  tokens = []

  # Remove front whitespace, somehow it confuses tokenizer
  s = s.lstrip()

  # accumulates all arguments in to the array
  accumulate = lambda *args: tokens.append(args)

  try:
    # Convert input into readline analog
    lines = s.split('\n')
    # Add '\n to all lines except last one.
    lines[:-1] = [line + '\n' for line in lines[:-1]]
    readline = (e for e in lines).next
    tokenize.tokenize(readline, accumulate)
  except tokenize.TokenError:
    # Tokenizer failed, usually an indication of not-terminated strings.
    # Remove all quotes and return the last sequence of not-spaces
    if not tokens:
      s = s.replace('"', ' ').replace("'", ' ').split()
      return s[-1] if s else ''
  except Exception:  # pylint: disable=broad-except
    # If all else fails, use poor's man tokenizer
    s = s.split()
    return s[-1] if s else ''

  # First we check if there is unfished quoted string
  for each in reversed(tokens):
    if each[_TOKEN_TYPE] == tokenize.ERRORTOKEN and each[_TOKEN] in {
        "'", '"', '"""', "'''"
    }:
      line = each[_TOKEN_END][0] - 1
      col = each[_TOKEN_END][1]
      return lines[line][col:]

  start_token = _find_expression_start(tokens)

  if start_token >= len(tokens):
    # This prevents us from generating random completions when there is
    # no completion to be generated
    return _last_real_token(tokens)

  start_pos = tokens[start_token][_TOKEN_START]

  first_line_index = start_pos[0] - 1
  if first_line_index >= len(lines):
    return _last_real_token(tokens)

  first_line = lines[first_line_index][start_pos[1]:]
  result = first_line + ''.join(lines[first_line_index + 1:])
  return result


class _CompletionSplitter(object):
  """Drop-in replacement for IPython CompletionSplitter replacement."""

  def __init__(self):
    # Used by ipython
    self.delims = ''

  def split_line(self, line, cursor_pos=None):
    """Split a line of text with a cursor at the given position."""
    l = line if cursor_pos is None else line[:cursor_pos]
    result = split(l)
    return result


_original_splitter = None


def enable(ip):
  """Installs completion splitter into IPython instance."""
  global _original_splitter
  if isinstance(ip.Completer.splitter, _CompletionSplitter):
    # Already installed
    return
  _original_splitter = ip.Completer.splitter
  ip.Completer.splitter = _CompletionSplitter()


def disable(ip):
  global _original_splitter
  if _original_splitter is None:
    return

  ip.Completer.splitter = _original_splitter
  _original_splitter = None
