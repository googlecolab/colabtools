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
"""Import hook for ensuring that Altair's Colab renderer is registered."""

import importlib
import logging
import os
import sys

from google.colab._import_hooks._hook_injector import HookInjectorLoader


class _AltairImportHook(importlib.abc.MetaPathFinder):
  """Enables Altair's Colab renderer upon import."""

  def find_spec(self, fullname, path=None, target=None):
    """Detects if altair.vegalite.* is being imported and enables the renderer."""
    if fullname not in [
        'altair.vegalite.v2',
        'altair.vegalite.v3',
        'altair.vegalite.v4',
        'altair.vegalite.v5',
    ]:
      return None

    def init_code_callback(module, previously_loaded):
      if not previously_loaded:
        try:
          module.renderers.enable('colab')
        except:  # pylint: disable=bare-except
          logging.exception('Error enabling Altair Colab renderer.')
          os.environ['COLAB_ALTAIR_IMPORT_HOOK_EXCEPTION'] = '1'

    loader = HookInjectorLoader(
        fullname,
        path,
        target,
        type(self),
        init_code_callback,
    )
    # If the module can't be found returning a loader will cause `import altair`
    # to succeed but with an empty module. Avoid that case by returning None.
    if not loader.find_spec():
      return None
    return importlib.util.spec_from_loader(fullname, loader)


def _register_hook():
  sys.meta_path = [_AltairImportHook()] + sys.meta_path
