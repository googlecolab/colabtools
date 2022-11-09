# Copyright 2018 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Import hook to add colab specific user agent."""

import imp  # pylint:disable=deprecated-module
import logging
import os
import sys

APPLICATION_NAME = 'google-colab'


class APICoreClientInfoImportHook:
  """Add Colab specific user agent for API analysis."""

  def find_module(self, fullname, path=None):
    if fullname not in ['google.api_core.client_info']:
      return None
    self.module_info = imp.find_module(fullname.split('.')[-1], path)
    return self

  def load_module(self, fullname):
    """Loads google.api_core.client_info and runs pre-initialization code.

    It loads google.api_core.client_info normally and modifies the to_user_agent
    method to include a Colab-specific string in the user agent.

    Args:
      fullname: fullname of the module
    Returns:
      A modified google.api_core.client_info module.
    """

    previously_loaded = fullname in sys.modules
    client_info_module = imp.load_module(fullname, *self.module_info)

    if not previously_loaded:
      try:
        old_to_user_agent = client_info_module.ClientInfo.to_user_agent

        def to_user_agent(self):
          return f'{APPLICATION_NAME} {old_to_user_agent(self)}'

        client_info_module.ClientInfo.to_user_agent = to_user_agent

      except:  # pylint: disable=bare-except
        logging.exception('Error user agent in google.api_core.client_info')
        os.environ['COLAB_BIGQUERY_CLIENT_IMPORT_HOOK_EXCEPTION'] = '1'

    return client_info_module


def _register_hook():
  sys.meta_path = [APICoreClientInfoImportHook()] + sys.meta_path
