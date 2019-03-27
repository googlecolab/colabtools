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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import functools
import imp
import importlib
import os
import sys
import unittest

from google.colab._import_hooks import _cv2


class OpenCVImportHookTest(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    super(OpenCVImportHookTest, cls).setUpClass()
    cls.orig_meta_path = sys.meta_path
    cls.orig_env = dict(os.environ)

    # Mock the cv amd cv2 imshow function for testing in environments where
    # the modules are not installed.
    class MockCV(object):
      """Simple mock of the cv2 module's imshow function."""

      @staticmethod
      def imshow(name, im):
        raise NotImplementedError()

    cls.find_module = imp.find_module
    cls.load_module = imp.load_module
    cls.cv_fake = False
    cls.cv2_fake = False

    @functools.wraps(imp.find_module)
    def find_module_mock(name, path):
      try:
        return cls.find_module(name, path)
      except ImportError:
        if name == "cv2":
          cls.cv2_fake = True
          return (None, "/path/to/fake/cv2", ("", "", 5))
        if name == "cv":
          cls.cv_fake = True
          return (None, "/path/to/fake/cv", ("", "", 5))
        raise

    @functools.wraps(imp.load_module)
    def load_module_mock(name, *module_info):
      if (name == "cv" and cls.cv_fake) or (name == "cv2" and cls.cv2_fake):
        sys.modules[name] = MockCV()
        return sys.modules[name]
      return cls.load_module(name, *module_info)

    imp.find_module = find_module_mock
    imp.load_module = load_module_mock

  @classmethod
  def tearDownClass(cls):
    super(OpenCVImportHookTest, cls).tearDownClass()
    imp.find_module = cls.find_module
    imp.load_module = cls.load_module

  def setUp(self):
    super(OpenCVImportHookTest, self).setUp()
    sys.meta_path = self.orig_meta_path

    os.environ.clear()
    os.environ.update(self.orig_env)

    sys.modules.pop("cv2", None)

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

  def testCVImshowDisabled(self):
    _cv2._register_hook()

    cv = importlib.import_module("cv")

    self.assertNotIn("COLAB_CV2_IMPORT_HOOK_EXCEPTION", os.environ)
    self.assertIn("cv", sys.modules)

    # Calling the function leads to the custom error.
    with self.assertRaises(_cv2.DisabledFunctionError) as err:
      cv.imshow()
    self.assertEqual(
        _cv2._OpenCVImportHook.message.format("cv"), str(err.exception))

    # After Enabling, we get a TypeError (because we pass no arguments).
    os.environ[_cv2._OpenCVImportHook.env_var] = "true"
    with self.assertRaises(TypeError) as err:
      cv.imshow()

  def testCV2ImshowDisabled(self):
    _cv2._register_hook()

    cv2 = importlib.import_module("cv2")

    self.assertNotIn("COLAB_CV2_IMPORT_HOOK_EXCEPTION", os.environ)
    self.assertIn("cv2", sys.modules)

    # Calling the function leads to the custom error.
    with self.assertRaises(_cv2.DisabledFunctionError) as err:
      cv2.imshow()
    self.assertEqual(
        _cv2._OpenCVImportHook.message.format("cv2"), str(err.exception))

    # After Enabling, we get a TypeError (because we pass no arguments).
    os.environ[_cv2._OpenCVImportHook.env_var] = "true"
    with self.assertRaises(TypeError) as err:
      cv2.imshow()
