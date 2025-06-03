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

import importlib
import os
import sys
import unittest
from unittest import mock

from google.colab._import_hooks import _bokeh


class BokehImportHookTest(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    super().setUpClass()
    cls.orig_meta_path = sys.meta_path
    cls.orig_env = dict(os.environ)

  def setUp(self):
    super().setUp()
    sys.meta_path = self.orig_meta_path

    os.environ.clear()
    os.environ.update(self.orig_env)

    sys.modules.pop('altair', None)
    self.addCleanup(mock.patch.stopall)

  def testRunsInitCodeOnImportWithFailure(self):
    _bokeh._register_hook()

    with self.assertRaises(ImportError):
      importlib.import_module('bokeh')

    self.assertNotIn('bokeh', sys.modules)
    self.assertNotIn('COLAB_BOKEH_IMPORT_HOOK_EXCEPTION', os.environ)

    # mock both bokeh and bokeh.io modules.
    mock_bokeh = mock.MagicMock()
    mock_bokeh.__path__ = '/tmp/bokeh'
    mock_bokeh_io = mock.MagicMock()

    def module_from_spec(spec):
      if spec.name == 'bokeh.io':
        return mock_bokeh_io

    with mock.patch.object(
        importlib.util, 'module_from_spec', side_effect=module_from_spec
    ):
      _mock_import('bokeh', mock_bokeh)
      _mock_import('bokeh.io', mock_bokeh_io)

    self.assertIn('bokeh', sys.modules)
    self.assertIn('bokeh.io', sys.modules)
    self.assertNotIn('COLAB_BOKEH_IMPORT_HOOK_EXCEPTION', os.environ)
    mock_bokeh_io.notebook.install_notebook_hook.assert_called_once()


def _mock_import(module, mock_module):
  sys.modules.pop(module, None)
  loader = mock.create_autospec(importlib.abc.Loader, instance=True)
  loader.create_module.return_value = mock_module
  # Loader doesn't define exec_module to avoid breaking backwards
  # compatibility. Use setattr to avoid the attribute error on mock.
  setattr(loader, 'exec_module', lambda module: None)
  module_spec = mock.create_autospec(
      importlib.machinery.ModuleSpec, instance=True
  )
  module_spec.name = module
  module_spec.loader = loader
  module_spec.submodule_search_locations = None
  module_spec._uninitialized_submodules = []

  # Fake meta_path spec finder.
  finder = mock.create_autospec(importlib.abc.MetaPathFinder, instance=True)
  # Finder doesn't define find_spec to avoid breaking backwards compatibility.
  # Use setattr to avoid the attribute error on mock.
  setattr(
      finder,
      'find_spec',
      lambda name, *_: module_spec if name == module else None,
  )
  sys.meta_path.append(finder)

  # Import again which should trigger the import hook.
  return importlib.import_module(module)
