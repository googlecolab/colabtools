"""Utility to add editor syntax highlighting to literal code strings.

Example:

    from google.colab import syntax
    query = syntax.sql('''
      SELECT * from tablename
    ''')
"""


def html(s):
  """Noop function to enable HTML highlighting for its argument."""
  return s


def javascript(s):
  """Noop function to enable JavaScript highlighting for its argument."""
  return s


def sql(s):
  """Noop function to enable SQL highlighting for its argument."""
  return s


def css(s):
  """Noop function to enable CSS highlighting for its argument."""
  return s
