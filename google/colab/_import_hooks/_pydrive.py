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

import imp
import logging
import os
import sys


class _PyDriveImportHook:
  """Patches PyDrive to allow credentials provided by Colab."""

  env_var = 'DISABLE_COLAB_PYDRIVE_CREDENTIALS_HOOK'

  def find_module(self, fullname, path=None):
    if fullname != 'pydrive.auth':
      return None
    uses_auth_ephem = os.environ.get('USE_AUTH_EPHEM', '0') == '1'
    if not uses_auth_ephem:
      return None
    self.module_info = imp.find_module(fullname.split('.')[-1], path)
    return self

  def load_module(self, name):
    """Loads PyDrive normally and runs pre-initialization code."""
    previously_loaded = name in sys.modules

    pydrive_auth_module = imp.load_module(name, *self.module_info)

    if not previously_loaded:
      try:
        import httplib2  # pylint:disable=g-import-not-at-top
        from oauth2client.contrib.gce import AppAssertionCredentials  # pylint:disable=g-import-not-at-top
        orig_local_webserver_auth = pydrive_auth_module.GoogleAuth.LocalWebserverAuth

        # Capture the environment variable outside of the patched method since
        # self will refer to a GoogleAuth object in these cases.
        env_var = self.env_var

        def PatchedLocalWebServerAuth(self, *args, **kwargs):  # pylint:disable=invalid-name
          if not os.environ.get(env_var, '') and isinstance(
              self.credentials, AppAssertionCredentials):
            self.credentials.refresh(httplib2.Http())
            return
          return orig_local_webserver_auth(self, *args, **kwargs)

        pydrive_auth_module.GoogleAuth.LocalWebserverAuth = PatchedLocalWebServerAuth
      except:  # pylint: disable=bare-except
        logging.exception('Error patching PyDrive')

    return pydrive_auth_module


def _register_hook():
  sys.meta_path = [_PyDriveImportHook()] + sys.meta_path
