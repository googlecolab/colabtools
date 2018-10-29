"""Functionality for working with user-defined snippets."""

from __future__ import absolute_import as _
from __future__ import division as _
from __future__ import print_function as _

from google.colab import _message

__all__ = ['register']


def register(url):
  """Add new snippets to the snippets pane from a notebook url.

  The snippets pane in Colab (visible with Ctrl-Alt-P) allows a colab user to
  search and insert snippets of code to do common tasks. This function will
  add new snippets to this menu, from any colab notebook URL accessible to the
  user. A notebook can contain multiple snippets, each under a markdown heading.

  Args:
    url: string. A URL that points to a saved Colab notebook
  """
  _message.blocking_request('register_snippets', {'url': url})
