# Copyright 2018 Google Inc.
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
"""TensorFlow helper magics.

Provides a %tensorflow_version line magic which allows the user to select which
version of TensorFlow will be loaded when they do 'import tensorflow as tf'.
"""

from __future__ import print_function

import sys
import textwrap

# The selected TF version
_tf_version = "1.x"

# A map of tensorflow version to installed location. If the installed
# location is empty, TensorflowMagics assumes that the package is available
# in sys.path already and no path hacks need to be done.
#
# This list must correspond to the TensorFlow installations on the host Colab
# instance.
_available_versions = {"1.x": "", "2.x": "/tensorflow-2.0.0b1"}


def _get_path(version):
  if version in _available_versions:
    location = _available_versions[version]
    if not location:
      return ""
    return "{}/python{}.{}".format(location, sys.version_info[0],
                                   sys.version_info[1])


def _tensorflow_version(line):
  """Implements the tensorflow_version line magic.

  If no parameter is specified, prints the currently selected and available
  TensorFlow versions. Otherwise, changes the selected version to the given
  version, if it exists.

  Args:
    line: the version parameter or the empty string.
  """
  global _tf_version

  line = line.strip()

  if not line:
    print("Currently selected TF version: {}".format(_tf_version))
    print("Available versions:\n* {}".format("\n* ".join(_available_versions)))
    return

  if line == _tf_version:
    # Nothing to do
    return

  if line not in _available_versions:
    old_line = line
    if line.startswith("1"):
      line = "1.x"
    if line.startswith("2"):
      line = "2.x"
    if line != old_line:
      print(
          textwrap.dedent("""\
        `%tensorflow_version` only switches the major version: `1.x` or `2.x`.
        You set: `{old_line}`. This will be interpreted as: `{line}`.

        """.format(old_line=old_line, line=line)))

  if line.lower() in _available_versions:
    if "tensorflow" in sys.modules:
      # TODO(b/132902517): add a 'restart runtime' button
      print("TensorFlow is already loaded. Please restart the runtime to "
            "change versions.")
    else:
      # If necessary, remove old path hacks.
      old_path = _get_path(_tf_version)
      if old_path:
        sys.path[:] = [e for e in sys.path if e != old_path]

      new_path = _get_path(line)
      if new_path:
        sys.path.insert(0, new_path)

      _tf_version = line
      print("TensorFlow {} selected.".format(line))
  else:
    print("Unknown TensorFlow version: {}".format(line))
    print("Currently selected TF version: {}".format(_tf_version))
    print("Available versions:\n * {}".format(
        "\n * ".join(_available_versions)))


def _register_magics(ip):
  ip.register_magic_function(
      _tensorflow_version, magic_kind="line", magic_name="tensorflow_version")
