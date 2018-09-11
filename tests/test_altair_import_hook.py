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
"""Tests for _AltairImportHook."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import importlib
import os
import sys
import unittest

from six.moves import reload_module

from google.colab._import_hooks import _altair


class AltairImportHookTest(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    cls.orig_meta_path = sys.meta_path
    cls.orig_env = dict(os.environ)

  def setUp(self):
    sys.meta_path = self.orig_meta_path

    os.environ.clear()
    os.environ.update(self.orig_env)

    sys.modules.pop('altair', None)

  def testRunsInitCodeOnImportWithFailure(self):
    _altair._register_hook()

    altair = importlib.import_module('altair')

    self.assertNotIn('COLAB_ALTAIR_IMPORT_HOOK_EXCEPTION', os.environ)
    self.assertIn('altair', sys.modules)
    self.assertEqual('colab', altair.renderers.active)

    # Reload of the module should not re-execute code.
    # Modify the active renderer and ensure that a reload doesn't reset it to
    # colab.
    altair.renderers.enable('default')
    self.assertEqual('default', altair.renderers.active)

    altair = reload_module(altair)
    self.assertNotIn('COLAB_ALTAIR_IMPORT_HOOK_EXCEPTION', os.environ)
    self.assertIn('altair', sys.modules)
    self.assertEqual('default', altair.renderers.active)
