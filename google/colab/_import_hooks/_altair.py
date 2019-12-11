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

import imp
import logging
import os
import sys


class _AltairImportHook(object):
  """Enables Altair's Colab renderer upon import."""

  def find_module(self, fullname, path=None):
    if fullname not in [
        'altair.vegalite.v2', 'altair.vegalite.v3', 'altair.vegalite.v4'
    ]:
      return None
    self.module_info = imp.find_module(fullname.split('.')[-1], path)
    return self

  def load_module(self, fullname):
    """Loads Altair normally and runs pre-initialization code."""
    previously_loaded = fullname in sys.modules
    altair_module = imp.load_module(fullname, *self.module_info)

    if not previously_loaded:
      try:
        altair_module.renderers.enable('colab')
      except:  # pylint: disable=bare-except
        logging.exception('Error enabling Altair Colab renderer.')
        os.environ['COLAB_ALTAIR_IMPORT_HOOK_EXCEPTION'] = '1'

    return altair_module


def _register_hook():
  sys.meta_path = [_AltairImportHook()] + sys.meta_path
