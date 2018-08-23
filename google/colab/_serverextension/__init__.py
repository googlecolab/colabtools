# Copyright 2018 Google Inc.
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
"""Colab-specific Jupyter serverextensions."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

# Allow imports of submodules without Jupyter
try:
  # pylint: disable=g-import-not-at-top
  from notebook import utils
  from notebook.base import handlers
  from google.colab._serverextension import _handlers
except ImportError:
  pass


def _jupyter_server_extension_paths():
  return [{
      'module': 'google.colab._serverextension',
  }]


def load_jupyter_server_extension(nb_server_app):
  """Called by Jupyter when starting the notebook manager."""
  app = nb_server_app.web_app

  url_maker = lambda path: utils.url_path_join(app.settings['base_url'], path)
  monitor_relative_path = '/api/colab/resources'

  app.add_handlers('.*$', [
      (url_maker(monitor_relative_path), _handlers.ResourceUsageHandler, {
          'kernel_manager': app.settings['kernel_manager']
      }),
  ])
  nb_server_app.log.info('google.colab serverextension initialized.')
