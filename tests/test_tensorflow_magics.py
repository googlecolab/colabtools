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

import collections
import os
import sys
import unittest

import requests

from google.colab import _tensorflow_magics

# pylint:disable=g-import-not-at-top
try:
  import unittest.mock as mock
except ImportError:
  import mock
# pylint:enable=g-import-not-at-top


class TensorflowMagicsTest(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    super(TensorflowMagicsTest, cls).setUpClass()
    cls._original_sys_path = sys.path[:]
    cls._original_os_path = os.environ.get("PATH", None)
    cls._original_os_pythonpath = os.environ.get("PYTHONPATH", None)
    os.environ["COLAB_TPU_ADDR"] = "0.0.0.0:8470"

  def setUp(self):
    super(TensorflowMagicsTest, self).setUp()
    _tensorflow_magics._instance = None

    _tensorflow_magics._get_tf_version = mock.Mock(
        return_value=_tensorflow_magics._VERSIONS["2"].version)
    fake_response = collections.namedtuple("FakeResponse", ["status_code"])
    requests.post = mock.Mock(return_value=fake_response(200))
    _tensorflow_magics._initialize()
    sys.path[:] = self._original_sys_path
    self._reset_env("PATH", self._original_os_path)
    self._reset_env("PYTHONPATH", self._original_os_pythonpath)

  def _reset_env(self, key, maybe_value):
    if maybe_value is None:
      os.environ.pop(key, None)
    else:
      os.environ[key] = maybe_value

  def _assert_starts_with(self, x, y):
    self.assertTrue(x.startswith(y), "%r does not start with %r" % (x, y))

  def _assert_ends_with(self, x, y):
    self.assertTrue(x.endswith(y), "%r does not end with %r" % (x, y))

  def _assert_len(self, xs, n):
    actual_len = len(xs)
    self.assertEqual(
        actual_len,
        n,
        "%r has length %r; expected %r" % (xs, actual_len, n),
    )

  def test_switch_2x_to_1x_no_paths(self):
    os.environ.pop("PATH", None)
    os.environ.pop("PYTHONPATH", None)
    tf1_path = _tensorflow_magics._VERSIONS["1"].path

    _tensorflow_magics._tensorflow_version("1.x")

    self.assertEqual(sys.path[1:], self._original_sys_path)
    self._assert_starts_with(sys.path[0], tf1_path)

    self._assert_starts_with(os.environ["PYTHONPATH"], tf1_path)
    self._assert_len(os.environ["PYTHONPATH"].split(os.pathsep), 1)

    os_path_head, os_path_tail = os.environ["PATH"].split(os.pathsep, 1)
    self._assert_starts_with(os_path_head, tf1_path)
    self._assert_ends_with(os_path_head, "bin")
    self.assertEqual(os_path_tail, "")

  def test_switch_2x_to_1x_existing_paths(self):
    original_pythonpath = os.pathsep.join(("/foo/bar", "/baz/quux"))
    original_os_path = os.pathsep.join(("/bar/foo", "/quux/baz"))
    os.environ["PYTHONPATH"] = original_pythonpath
    os.environ["PATH"] = original_os_path
    tf1_path = _tensorflow_magics._VERSIONS["1"].path

    _tensorflow_magics._tensorflow_version("1.x")

    self.assertEqual(sys.path[1:], self._original_sys_path)
    self._assert_starts_with(sys.path[0], tf1_path)

    (pythonpath_head,
     pythonpath_tail) = os.environ["PYTHONPATH"].split(os.pathsep, 1)
    self._assert_starts_with(pythonpath_head, tf1_path)
    self.assertEqual(pythonpath_tail, original_pythonpath)

    os_path_head, os_path_tail = os.environ["PATH"].split(os.pathsep, 1)
    self._assert_starts_with(os_path_head, tf1_path)
    self._assert_ends_with(os_path_head, "bin")
    self.assertEqual(os_path_tail, original_os_path)

  def test_switch_back_no_paths(self):
    os.environ.pop("PATH", None)
    os.environ.pop("PYTHONPATH", None)

    _tensorflow_magics._tensorflow_version("1.x")
    _tensorflow_magics._tensorflow_version("2.x")

    self.assertEqual(sys.path, self._original_sys_path)
    self.assertEqual(os.environ.get("PATH", ""), "")
    self.assertEqual(os.environ.get("PYTHONPATH", ""), "")

  def test_switch_back_with_paths(self):
    original_pythonpath = os.pathsep.join(("/foo/bar", "/baz/quux"))
    original_os_path = os.pathsep.join(("/bar/foo", "/quux/baz"))
    os.environ["PYTHONPATH"] = original_pythonpath
    os.environ["PATH"] = original_os_path

    _tensorflow_magics._tensorflow_version("1.x")
    _tensorflow_magics._tensorflow_version("2.x")

    self.assertEqual(sys.path, self._original_sys_path)
    self.assertEqual(os.environ["PATH"], original_os_path)
    self.assertEqual(os.environ["PYTHONPATH"], original_pythonpath)

  def test_switch_back_does_not_import(self):
    _tensorflow_magics._tensorflow_version("2.x")
    _tensorflow_magics._tensorflow_version("1.x")

    self.assertNotIn("tensorflow", sys.modules)

  def test_tpu_version_switch(self):
    _tensorflow_magics._get_tf_version = mock.Mock(
        return_value=_tensorflow_magics._VERSIONS["1"].version)
    _tensorflow_magics._tensorflow_version("1.x")
    _tensorflow_magics._get_tf_version = mock.Mock(
        return_value=_tensorflow_magics._VERSIONS["2"].version)
    _tensorflow_magics._tensorflow_version("2.x")

    expected = "http://0.0.0.0:8475/requestversion/{}"
    calls = [
        mock.call(expected.format(_tensorflow_magics._VERSIONS["1"].version)),
        mock.call(expected.format(_tensorflow_magics._VERSIONS["2"].version)),
    ]
    self.assertEqual(requests.post.mock_calls, calls)

if __name__ == "__main__":
  unittest.main()
