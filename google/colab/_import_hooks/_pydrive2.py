# Copyright 2022 Google Inc. All rights reserved.
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
"""Import hook to allow credentials provided by Colab."""

import importlib
import logging
import os
import sys

from google.colab._import_hooks._hook_injector import HookInjectorLoader


class _PyDrive2ImportHook(importlib.abc.MetaPathFinder):
  """Patches PyDrive2 to allow credentials provided by Colab."""

  env_var = 'DISABLE_COLAB_PYDRIVE2_CREDENTIALS_HOOK'

  def find_spec(self, fullname, path=None, target=None):
    """
    Finds a spec for pydrive2.auth and hooks the module loader.

    Returns:
      A spec for the module if it can be found by another meta path finder,
      otherwise None to prevent an empty module being loaded.
    """
    if fullname != 'pydrive2.auth':
      return None

    uses_auth_ephem = os.environ.get('USE_AUTH_EPHEM', '0') == '1'
    if not uses_auth_ephem:
      return None

    def init_code_callback(module, previously_loaded):
      """Loads PyDrive2 normally and runs pre-initialization code."""
      if not previously_loaded:
        try:
          import httplib2  # pylint:disable=g-import-not-at-top
          from oauth2client.contrib.gce import AppAssertionCredentials  # pylint:disable=g-import-not-at-top

          orig_local_webserver_auth = module.GoogleAuth.LocalWebserverAuth

          # Capture the environment variable outside of the patched method since
          # self will refer to a GoogleAuth object in these cases.
          env_var = self.env_var

          def PatchedLocalWebServerAuth(self, *args, **kwargs):  # pylint:disable=invalid-name
            if not os.environ.get(env_var, '') and isinstance(
                self.credentials, AppAssertionCredentials
            ):
              self.credentials.refresh(httplib2.Http())
              return
            return orig_local_webserver_auth(self, *args, **kwargs)

          module.GoogleAuth.LocalWebserverAuth = PatchedLocalWebServerAuth
        except:  # pylint: disable=bare-except
          logging.exception('Error patching PyDrive')

    loader = HookInjectorLoader(
        fullname,
        path,
        target,
        type(self),
        init_code_callback,
    )
    if not loader.find_spec():
      return None
    return importlib.util.spec_from_loader(fullname, loader)


def _register_hook():
  sys.meta_path = [_PyDrive2ImportHook()] + sys.meta_path
