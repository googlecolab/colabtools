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

import os
import sys
import textwrap

# The selected TF version
_tf_version = "1.x"
_explicitly_set = False

# A map of tensorflow version to installed location. If the installed
# location is `None`, TensorflowMagics assumes that the package is
# available in sys.path already and no path hacks need to be done.
#
# This list must correspond to the TensorFlow installations on the host Colab
# instance.
_available_versions = {"1.x": None, "2.x": "/tensorflow-2.0.0"}


def _get_python_path(version):
  """Gets the Python path entry for TensorFlow modules.

  Args:
    version: A version string, which should be a key of `_available_versions`.

  Returns:
    A string suitable for inclusion in the `PYTHONPATH` environment
    variable or in `sys.path`, or `None` if no path manipulation is
    required to use the provided version of TensorFlow.

  Raises:
    KeyError: If `version` is not a key of `_available_versions`.
  """
  location = _available_versions[version]
  if location is None:
    return None
  return os.path.join(
      location, "python{}.{}".format(sys.version_info[0], sys.version_info[1]))


def _get_os_path(version):
  """Gets the OS path entry for TensorFlow binaries.

  Args:
    version: A version string, which should be a key of `_available_versions`.

  Returns:
    A string suitable for inclusion in the `PATH` environment variable,
    or `None` if no path manipulation is required to use binaries from
    the provided version of TensorFlow.

  Raises:
    KeyError: If `version` is not a key of `_available_versions`.
  """
  python_path = _get_python_path(version)
  if python_path is None:
    return None
  return os.path.join(python_path, "bin")


def _drop_and_prepend(xs, to_drop, to_prepend):
  """Filters a list in place (maybe), then prepend an element (maybe).

  Args:
    xs: A list to mutate in place.
    to_drop: A string to remove from `xs` (all occurrences), or `None` to not
      drop anything.
    to_prepend: A string to prepend to `xs`, or `None` to not prepend anything.
  """
  if to_drop is not None:
    xs[:] = [x for x in xs if x != to_drop]
  if to_prepend is not None:
    xs.insert(0, to_prepend)


def _drop_and_prepend_env(key, to_drop, to_prepend, empty_includes_cwd):
  """Like `_drop_and_prepend_env`, but mutate an environment variable.

  Args:
    key: The environment variable to modify.
    to_drop: A path component to remove from the environment variable (all
      occurrences), or `None` to not drop anything.
    to_prepend: A path component to prepend to the environment variable, or
      `None` to not prepend anything.
    empty_includes_cwd: Whether the semantics of the given environment variable
      treat an unset or empty value as including the current working directory
      (as with POSIX `$PATH`) or not (as with Python 3 `$PYTHONPATH`).
  """
  env_value = os.environ.get(key, "")
  if env_value:
    parts = env_value.split(os.pathsep)
  else:
    parts = [""] if empty_includes_cwd else []
  _drop_and_prepend(parts, to_drop, to_prepend)
  os.environ[key] = os.pathsep.join(parts)


def _tensorflow_version(line):
  """Implements the tensorflow_version line magic.

  If no parameter is specified, prints the currently selected and available
  TensorFlow versions. Otherwise, changes the selected version to the given
  version, if it exists.

  Args:
    line: the version parameter or the empty string.
  """
  global _tf_version
  global _explicitly_set

  line = line.strip()

  if not line:
    print("Currently selected TF version: {}".format(_tf_version))
    print("Available versions:\n* {}".format("\n* ".join(_available_versions)))
    return

  _explicitly_set = True
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

  if line in _available_versions:
    if "tensorflow" in sys.modules:
      # TODO(b/132902517): add a 'restart runtime' button
      print("TensorFlow is already loaded. Please restart the runtime to "
            "change versions.")
    else:
      old_python_path = _get_python_path(_tf_version)
      new_python_path = _get_python_path(line)

      old_os_path = _get_os_path(_tf_version)
      new_os_path = _get_os_path(line)

      # Fix up `sys.path`, for Python imports within this process.
      _drop_and_prepend(sys.path, old_python_path, new_python_path)

      # Fix up `$PYTHONPATH`, for Python imports in subprocesses.
      _drop_and_prepend_env(
          "PYTHONPATH",
          old_python_path,
          new_python_path,
          empty_includes_cwd=False)

      # Fix up `$PATH`, for locations of subprocess binaries.
      _drop_and_prepend_env(
          "PATH", old_os_path, new_os_path, empty_includes_cwd=True)

      _tf_version = line
      print("TensorFlow {} selected.".format(line))
  else:
    print("Unknown TensorFlow version: {}".format(line))
    print("Currently selected TF version: {}".format(_tf_version))
    print("Available versions:\n * {}".format(
        "\n * ".join(_available_versions)))


def explicitly_set():
  return _explicitly_set


def _register_magics(ip):
  ip.register_magic_function(
      _tensorflow_version, magic_kind="line", magic_name="tensorflow_version")
