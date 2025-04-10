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
"""Tests for _OpenCVImportHook."""

import importlib
import os
import sys
import unittest
from unittest import mock
from absl.testing import parameterized
from google.colab._import_hooks import _cv2


class DisableFunctionTest(unittest.TestCase):

  def testDisableFunction(self):
    def a_very_bad_func():
      return "did a bad thing"

    reason = "You should not do this."
    env_var = "ENABLE_BAD_FUNC"
    disabled_func = _cv2.disable_function(a_very_bad_func, reason, env_var)

    with self.assertRaises(_cv2.DisabledFunctionError) as err:
      disabled_func()
    self.assertIn(reason, str(err.exception))
    self.assertIn(reason, str(err.exception))

    os.environ[env_var] = "true"
    self.assertEqual(disabled_func(), a_very_bad_func())


class OpenCVImportHookTest(parameterized.TestCase):

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

    sys.modules.pop("cv", None)
    sys.modules.pop("cv2", None)

    self.addCleanup(mock.patch.stopall)

  @parameterized.named_parameters(
      ("CV", "cv"),
      ("CV2", "cv2"),
  )
  def testImshowDisabled_(self, module):
    _cv2._register_hook()
    cv = _import_or_mock_module(module, _MockCV)

    self.assertNotIn("COLAB_CV2_IMPORT_HOOK_EXCEPTION", os.environ)
    self.assertIn(module, sys.modules)

    # Calling the function leads to the custom error.
    with self.assertRaises(_cv2.DisabledFunctionError) as err:
      cv.imshow()
    self.assertEqual(
        _cv2._OpenCVImportHook.message.format(module), str(err.exception)
    )

    os.environ[_cv2._OpenCVImportHook.env_var] = "true"
    # After enabling, should raises an error because wrong number of arguments.
    with self.assertRaises((TypeError, cv.error)):
      cv.imshow()


# Mock the cv amd cv2 imshow function for testing in environments where
# the modules are not installed.
class _MockCV:
  """Simple mock of the cv2 module's imshow function."""

  error = TypeError

  @staticmethod
  def imshow(name=None, im=None):
    raise _MockCV.error()


def _import_or_mock_module(module, module_mock):
  try:
    return importlib.import_module(module)
  except ImportError:
    # We'll setup a mock for the module.
    pass

  sys.modules.pop(module, None)
  loader = mock.create_autospec(importlib.abc.Loader, instance=True)
  # Loader doesn't define exec_module to avoid breaking backwards
  # compatibility. Use setattr to avoid the attribute error on mock.
  setattr(loader, "exec_module", lambda module: None)
  module_spec = mock.create_autospec(
      importlib.machinery.ModuleSpec, instance=True
  )
  module_spec.loader = loader

  # Fake meta_path spec finder.
  finder = mock.create_autospec(importlib.abc.MetaPathFinder, instance=True)
  # Finder doesn't define find_spec to avoid breaking backwards compatibility.
  # Use setattr to avoid the attribute error on mock.
  setattr(
      finder,
      "find_spec",
      lambda name, path, target: module_spec if name == module else None,
  )
  sys.meta_path.append(finder)

  mock_module = module_mock()
  mock.patch.object(
      importlib.util, "module_from_spec", return_value=mock_module
  ).start()

  # Import again which should trigger the import hook.
  return importlib.import_module(module)
