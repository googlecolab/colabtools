"""Colab Python APIs."""

from google.colab import auth
from google.colab import files

__all__ = ['auth', 'files']

__version__ = '0.0.1a2'


def _jupyter_nbextension_paths():
  # See:
  # http://testnb.readthedocs.io/en/latest/examples/Notebook/Distributing%20Jupyter%20Extensions%20as%20Python%20Packages.html#Defining-the-server-extension-and-nbextension
  return [dict(section='notebook', src='resources', dest='google.colab')]
