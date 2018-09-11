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
"""Tests for _TensorFlowImportHook."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import importlib
import os
import sys
import unittest

from six.moves import reload_module

from google.colab._import_hooks import _tensorflow

#  pylint:disable=g-import-not-at-top
try:
  from unittest import mock
except ImportError:
  import mock
#  pylint:enable=g-import-not-at-top


class TensorFlowImportHookTest(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    cls.orig_meta_path = sys.meta_path
    cls.orig_env = dict(os.environ)

  def setUp(self):
    sys.meta_path = self.orig_meta_path

    os.environ.clear()
    os.environ.update(self.orig_env)

    # The TensorFlow module interacts poorly with calls to reload(). Use the
    # termios module instead since we're mostly concerned with testing that
    # the custom import hook is registered and run.
    sys.modules.pop('termios', None)

  @mock.patch.object(_tensorflow._TensorFlowImportHook, 'load_module')
  @mock.patch.object(
      _tensorflow._TensorFlowImportHook, '_has_gpu', return_value=True)
  def testDoesNothingWithEnvVariableSet(self, unused_mock_has_gpu,
                                        mock_load_module):
    os.environ['DISABLE_COLAB_TF_IMPORT_HOOK'] = '1'
    _tensorflow._register_hook(module_name='termios')

    importlib.import_module('termios')

    mock_load_module.assert_not_called()
    # Default system import hooks are still called, even if the custom hook was
    # skipped.
    self.assertIn('termios', sys.modules)

  @mock.patch.object(_tensorflow._TensorFlowImportHook, 'load_module')
  @mock.patch.object(
      _tensorflow._TensorFlowImportHook, '_has_gpu', return_value=False)
  def testDoesNothingWithNoNvidiaDevicePresent(self, unused_mock_has_gpu,
                                               mock_load_module):
    _tensorflow._register_hook(module_name='termios')

    importlib.import_module('termios')
    # Default system import hooks are still called, even if the custom hook was
    # skipped.
    self.assertIn('termios', sys.modules)

    mock_load_module.assert_not_called()

  @mock.patch.object(
      _tensorflow._TensorFlowImportHook, '_has_gpu', return_value=True)
  def testRunsInitCodeOnImportWithFailure(self, unused_mock_has_gpu):
    _tensorflow._register_hook(module_name='termios')

    # Relevant TensorFlow code is not present in the termios module. This
    # test asserts that the import hook is run and handles exceptions if the
    # code it's executing fails.
    importlib.import_module('termios')

    self.assertNotIn('COLAB_TF_IMPORT_HOOK_STARTUP_DURATION', os.environ)
    self.assertIn('COLAB_TF_IMPORT_HOOK_EXCEPTION', os.environ)
    self.assertIn('termios', sys.modules)

    # Reload of the module should not re-execute code.
    # Clear the environment variables set by the import hook to see whether they
    # run again.
    os.environ.clear()
    os.environ.update(self.orig_env)

    reload_module(sys.modules['termios'])
    self.assertNotIn('COLAB_TF_IMPORT_HOOK_STARTUP_DURATION', os.environ)
    self.assertNotIn('COLAB_TF_IMPORT_HOOK_EXCEPTION', os.environ)
    self.assertIn('termios', sys.modules)
