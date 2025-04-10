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

import importlib
import logging
import os
import sys

from google.colab._import_hooks._hook_injector import HookInjectorLoader

APPLICATION_NAME = 'google-colab'


class APICoreClientInfoImportHook(importlib.abc.MetaPathFinder):
  """Add Colab specific user agent for API analysis."""

  def find_spec(self, fullname, path=None, target=None):
    """Loads google.api_core.client_info and runs pre-initialization code.

    It loads google.api_core.client_info normally and modifies the to_user_agent
    method to include a Colab-specific string in the user agent.

    Args:
      fullname: fullname of the module
      path: path to the module
      target: target of the module

    Returns:
      A ModuleSpec for google.api_core.client_info.
    """
    if fullname not in ['google.api_core.client_info']:
      return None

    def init_code_callback(module, previously_loaded):
      if not previously_loaded:
        try:
          old_to_user_agent = module.ClientInfo.to_user_agent

          def to_user_agent(self):
            return f'{APPLICATION_NAME} {old_to_user_agent(self)}'

          module.ClientInfo.to_user_agent = to_user_agent

        except:  # pylint: disable=bare-except
          logging.exception('Error user agent in google.api_core.client_info')
          os.environ['COLAB_BIGQUERY_CLIENT_IMPORT_HOOK_EXCEPTION'] = '1'

    loader = HookInjectorLoader(
        fullname,
        path,
        target,
        type(self),
        init_code_callback,
    )
    # If the module can't be found returning a loader will cause the import to
    # succeed but with an empty module. Avoid that case by returning None.
    if not loader.find_spec():
      return None
    return importlib.util.spec_from_loader(fullname, loader)


def _register_hook():
  sys.meta_path = [APICoreClientInfoImportHook()] + sys.meta_path
