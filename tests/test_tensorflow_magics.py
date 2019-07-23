# Copyright 2019 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for the `%tensorflow_version` magic."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import sys
import unittest

from google.colab import _tensorflow_magics


class TensorflowMagicsTest(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    super(TensorflowMagicsTest, cls).setUpClass()
    cls._original_version = _tensorflow_magics._tf_version
    cls._original_sys_path = sys.path[:]

  def setUp(self):
    super(TensorflowMagicsTest, self).setUp()
    _tensorflow_magics._tf_version = self._original_version
    sys.path[:] = self._original_sys_path

  def test_switch_1x_to_2x(self):
    _tensorflow_magics._tensorflow_version("2.x")
    tf2_path = _tensorflow_magics._available_versions["2.x"]
    self.assertEqual(sys.path[1:], self._original_sys_path)
    self.assertTrue(sys.path[0].startswith(tf2_path), (sys.path[0], tf2_path))

  def test_switch_back(self):
    _tensorflow_magics._tensorflow_version("2.x")
    _tensorflow_magics._tensorflow_version("1.x")
    self.assertEqual(sys.path, self._original_sys_path)


if __name__ == "__main__":
  unittest.main()
