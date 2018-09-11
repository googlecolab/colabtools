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
"""Colab Python APIs."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from google.colab import _import_hooks
from google.colab import _shell_customizations
from google.colab import _system_commands
from google.colab import auth
from google.colab import files
from google.colab import output
from google.colab import widgets

__all__ = ['auth', 'files', 'output', 'widgets']

__version__ = '0.0.1a2'


def _jupyter_nbextension_paths():
  # See:
  # http://testnb.readthedocs.io/en/latest/examples/Notebook/Distributing%20Jupyter%20Extensions%20as%20Python%20Packages.html#Defining-the-server-extension-and-nbextension
  return [{
      'dest': 'google.colab',
      'section': 'notebook',
      'src': 'resources',
  }]


def load_ipython_extension(ipython):
  """Called by IPython when this module is loaded as an IPython extension."""
  _shell_customizations.initialize()
  _system_commands._register_magics(ipython)  # pylint:disable=protected-access
  _import_hooks._register_hooks()  # pylint:disable=protected-access
