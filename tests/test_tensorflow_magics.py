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
    _tensorflow_magics._get_tf_version = mock.Mock(
        return_value=_tensorflow_magics._VERSIONS["2"].version)

    # TODO(b/141887595): Remove this comment when it is no longer true (i.e.
    # when TF2 becomes the default).
    # All prefixed with 1.x directory by default.
    _tensorflow_magics._instance = None
    _tensorflow_magics._initialize()
    cls._original_sys_path = sys.path[:]
    cls._original_os_path = os.environ.get("PATH", None)
    cls._original_os_pythonpath = os.environ.get("PYTHONPATH", None)
    os.environ["COLAB_TPU_ADDR"] = "0.0.0.0:8470"

  def setUp(self):
    super(TensorflowMagicsTest, self).setUp()
    _tensorflow_magics._instance = None

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

  def test_paths_post_init(self):
    _tensorflow_magics._instance = None
    _tensorflow_magics._initialize()

    tf1_path = _tensorflow_magics._VERSIONS["1"].path

    self._assert_starts_with(sys.path[0], tf1_path)
    path_head = os.environ["PATH"].split(os.pathsep)[0]
    self._assert_starts_with(path_head, tf1_path)
    self._assert_ends_with(path_head, "bin")
    self._assert_starts_with(os.environ["PYTHONPATH"].split(os.pathsep)[0],
                             tf1_path)

  def test_switch_1x_to_2x_default_path(self):
    _tensorflow_magics._tensorflow_version("2.x")

    self.assertEqual(sys.path, self._original_sys_path[1:])
    self.assertEqual(
        os.environ["PATH"],
        os.pathsep.join(self._original_os_path.split(os.pathsep, 1)[1:]))
    self.assertEqual(
        os.environ["PYTHONPATH"],
        os.pathsep.join(self._original_os_pythonpath.split(os.pathsep, 1)[1:]))

  def test_switch_1x_to_2x_modified_path(self):
    new_path = os.pathsep.join(("/bar/foo", "quux/baz"))
    os.environ["PATH"] = os.pathsep.join((new_path, self._original_os_path))
    os.environ["PYTHONPATH"] = os.pathsep.join(
        (new_path, self._original_os_pythonpath))

    _tensorflow_magics._tensorflow_version("2.x")

    self.assertEqual(sys.path, self._original_sys_path[1:])
    self.assertEqual(
        os.environ["PATH"],
        os.pathsep.join([new_path] +
                        self._original_os_path.split(os.pathsep, 1)[1:]))
    self.assertEqual(
        os.environ["PYTHONPATH"],
        os.pathsep.join([new_path] +
                        self._original_os_pythonpath.split(os.pathsep, 1)[1:]))

  def test_switch_back_default_path(self):
    _tensorflow_magics._tensorflow_version("2.x")
    _tensorflow_magics._tensorflow_version("1.x")

    self.assertEqual(sys.path, self._original_sys_path)
    self.assertEqual(os.environ["PATH"], self._original_os_path)
    self.assertEqual(os.environ["PYTHONPATH"], self._original_os_pythonpath)

  def test_switch_back_modified_path(self):
    new_path = os.pathsep.join(("/bar/foo", "quux/baz"))
    os.environ["PATH"] = os.pathsep.join((new_path, self._original_os_path))
    os.environ["PYTHONPATH"] = os.pathsep.join(
        (new_path, self._original_os_pythonpath))

    _tensorflow_magics._tensorflow_version("2.x")
    _tensorflow_magics._tensorflow_version("1.x")

    tf1_path = _tensorflow_magics._VERSIONS["1"].path

    self._assert_starts_with(sys.path[0], tf1_path)
    self.assertEqual(sys.path, self._original_sys_path)

    (path_head, path_tail) = os.environ["PATH"].split(os.pathsep, 1)
    self._assert_starts_with(path_head, tf1_path)
    self._assert_ends_with(path_head, "bin")
    self.assertEqual(
        path_tail,
        os.pathsep.join([new_path] +
                        self._original_os_path.split(os.pathsep, 1)[1:]))
    (pythonpath_head,
     pythonpath_tail) = os.environ["PYTHONPATH"].split(os.pathsep, 1)
    self._assert_starts_with(pythonpath_head, tf1_path)
    self.assertEqual(
        pythonpath_tail,
        os.pathsep.join([new_path] +
                        self._original_os_pythonpath.split(os.pathsep, 1)[1:]))

  def test_handle_tf_install_post_init(self):
    _tensorflow_magics._handle_tf_install()

    # Path should revert to being un-prefixed.
    self.assertFalse(_tensorflow_magics._explicitly_set())
    self.assertEqual(sys.path, self._original_sys_path[1:])
    self.assertEqual(
        os.environ["PATH"],
        os.pathsep.join(self._original_os_path.split(os.pathsep, 1)[1:]))
    self.assertEqual(
        os.environ["PYTHONPATH"],
        os.pathsep.join(self._original_os_pythonpath.split(os.pathsep, 1)[1:]))

  def test_handle_tf_install_multiple_calls(self):
    _tensorflow_magics._handle_tf_install()
    _tensorflow_magics._handle_tf_install()

    # Path should be un-prefixed, no errors should be raised.
    self.assertFalse(_tensorflow_magics._explicitly_set())
    self.assertEqual(sys.path, self._original_sys_path[1:])
    self.assertEqual(
        os.environ["PATH"],
        os.pathsep.join(self._original_os_path.split(os.pathsep, 1)[1:]))
    self.assertEqual(
        os.environ["PYTHONPATH"],
        os.pathsep.join(self._original_os_pythonpath.split(os.pathsep, 1)[1:]))

  def test_handle_tf_install_after_setting_version(self):
    _tensorflow_magics._tensorflow_version("1.x")
    _tensorflow_magics._handle_tf_install()

    # _handle_tf_install should be a no-op because magic was invoked.
    self.assertTrue(_tensorflow_magics._explicitly_set())
    tf1_path = _tensorflow_magics._VERSIONS["1"].path

    self._assert_starts_with(sys.path[0], tf1_path)
    path_head = os.environ["PATH"].split(os.pathsep)[0]
    self._assert_starts_with(path_head, tf1_path)
    self._assert_ends_with(path_head, "bin")
    self._assert_starts_with(os.environ["PYTHONPATH"].split(os.pathsep)[0],
                             tf1_path)

  def test_switch_back_does_not_import(self):
    _tensorflow_magics._tensorflow_version("2.x")
    _tensorflow_magics._tensorflow_version("1.x")

    self.assertNotIn("tensorflow", sys.modules)

  def test_tpu_version_switch(self):
    _tensorflow_magics._get_tf_version = mock.Mock(
        return_value=_tensorflow_magics._VERSIONS["2"].version)
    _tensorflow_magics._tensorflow_version("2.x")
    _tensorflow_magics._get_tf_version = mock.Mock(
        return_value=_tensorflow_magics._VERSIONS["1"].version)
    _tensorflow_magics._tensorflow_version("1.x")

    expected = "http://0.0.0.0:8475/requestversion/{}"
    calls = [
        mock.call(expected.format(_tensorflow_magics._VERSIONS["2"].version)),
        mock.call(expected.format(_tensorflow_magics._VERSIONS["1"].version)),
    ]
    self.assertEqual(requests.post.mock_calls, calls)


if __name__ == "__main__":
  unittest.main()
