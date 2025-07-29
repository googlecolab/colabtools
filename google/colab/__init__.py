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

import logging
import os
import pathlib

from google.colab import _import_hooks
from google.colab import _import_magics
from google.colab import _installation_commands
from google.colab import _interactive_table_hint_button
from google.colab import _reprs
from google.colab import _serverextension
from google.colab import _shell_customizations
from google.colab import _system_commands
from google.colab import _tensorflow_magics
from google.colab import auth
from google.colab import autoviz
from google.colab import data_table
from google.colab import drive
from google.colab import files
from google.colab import output
from google.colab import runtime
from google.colab import snippets
from google.colab import widgets


__all__ = [
    'auth',
    'autoviz',
    'data_table',
    'drive',
    'files',
    'output',
    'runtime',
    'snippets',
    'widgets',
]

__version__ = '0.0.1a2'


def _jupyter_nbextension_paths():
  # See:
  # http://testnb.readthedocs.io/en/latest/examples/Notebook/Distributing%20Jupyter%20Extensions%20as%20Python%20Packages.html#Defining-the-server-extension-and-nbextension
  return [{
      'dest': 'google.colab',
      'section': 'notebook',
      'src': 'resources',
  }]


def _jupyter_server_extension_points():
  return [
      {
          'module': 'google.colab',
      },
  ]


def load_jupyter_server_extension(server_app):
  """Called by Jupyter server to handle the static file requests for tabbar."""
  # We only want to import these modules when setting up a server extension, and
  # want to avoid raising an exception when the `jupyter_server` package isn't
  # available.
  # pylint: disable=g-import-not-at-top
  # pytype: disable=import-error
  from jupyter_server import utils
  from jupyter_server.base import handlers
  # pytype: enable=import-error
  # pylint: enable=g-import-not-at-top

  # pylint: disable=protected-access
  server_app.log.addFilter(_serverextension._ColabLoggingFilter())
  # pylint: enable=protected-access
  resources_path = os.path.join(
      pathlib.Path(__file__).parent.absolute(), 'resources'
  )
  url_maker = lambda path: utils.url_path_join(
      server_app.web_app.settings['base_url'], path
  )
  # For backwards compatibility, we will serve the static files for the
  # tabbar from the nbextension path.
  # See google/colab/widgets/_tabbar.py
  nbextension = url_maker('/nbextensions/google.colab/(.*)')
  server_app.web_app.add_handlers(
      '.*$',
      [
          (
              nbextension,
              handlers.FileFindHandler,
              {'path': resources_path, 'no_cache_paths': ['/']},
          ),
      ],
  )


def load_ipython_extension(ipython):
  """Called by IPython when this module is loaded as an IPython extension."""
  _import_magics._declare_colabx_magics()  # pylint:disable=protected-access
  _shell_customizations.initialize()
  _system_commands._register_magics(ipython)  # pylint:disable=protected-access
  _installation_commands._register_magics(ipython)  # pylint:disable=protected-access
  _import_hooks._register_hooks()  # pylint:disable=protected-access
  _tensorflow_magics._register_magics(ipython)  # pylint:disable=protected-access
  _reprs.enable_string_repr()
  # TODO: remove workaround when pandas fixes this issue.
  _reprs.enable_df_style_formatter()
  _reprs.enable_pandas_series_repr()
  _interactive_table_hint_button._enable_df_interactive_hint_formatter()  # pylint:disable=protected-access
