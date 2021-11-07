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

import collections
import os
import sys
import textwrap

import pkg_resources

# A map of tensorflow version to installed location. If the installed
# location is `None`, TensorflowMagics assumes that the package is
# available in sys.path by default.
#
# This list must correspond to the TensorFlow installations on the host Colab
# instance.
_VersionInfo = collections.namedtuple("_VersionInfo",
                                      ["name", "path", "version"])
_VERSIONS = {
    "1": _VersionInfo("1.x", "/tensorflow-1.15.2", "1.15.2"),
    "2": _VersionInfo("2.x", None, "2.7.0"),
}

_DEFAULT_VERSION = _VERSIONS["2"]
_INSTALLED_VERSION = _VERSIONS["2"]


def _get_python_path(version):
  """Gets the Python path entry for TensorFlow modules.

  Args:
    version: A _VersionInfo object representing a version of TF.

  Returns:
    A string suitable for inclusion in the `PYTHONPATH` environment
    variable or in `sys.path`, or `None` if no path manipulation is
    required to use the provided version of TensorFlow.
  """
  if version.path is None:
    return None
  return os.path.join(
      version.path, "python{}.{}".format(sys.version_info[0],
                                         sys.version_info[1]))


def _get_os_path(version):
  """Gets the OS path entry for TensorFlow binaries.

  Args:
    version: A _VersionInfo object representing a version of TF.

  Returns:
    A string suitable for inclusion in the `PATH` environment variable,
    or `None` if no path manipulation is required to use binaries from
    the provided version of TensorFlow.
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


def _get_tf_version():
  """Get the current tensorflow version via pkg_resources."""
  # pkg_resources.get_distribution uses sys.path at the time pkg_resources was
  # imported, so we constsruct our own WorkingSet here.
  tf_dist = pkg_resources.WorkingSet(sys.path).find(
      pkg_resources.Requirement.parse("tensorflow"))
  if tf_dist is None:
    return None
  return tf_dist.version


_instance = None


class _TFVersionManager(object):
  """Class that manages the TensorFlow version used by Colab."""

  def __init__(self):
    self._version = _DEFAULT_VERSION
    self.explicitly_set = False

  def _maybe_switch_tpu_version(self, version):
    """Switch the TPU TF version (if needed)."""
    # Avoid forcing a kernel restart on users updating requests if they haven't
    # yet used our TF magics.
    import requests  # pylint: disable=g-import-not-at-top
    if "COLAB_TPU_ADDR" not in os.environ:
      return
    # See b/141173168 for why this path.
    url = "http://{}:8475/requestversion/{}".format(
        os.environ["COLAB_TPU_ADDR"].split(":")[0], version)
    resp = requests.post(url)
    if resp.status_code != 200:
      print("Failed to switch the TPU to TF {}".format(version))

  def _set_version(self, version):
    """Perform version change by manipulating PATH/PYTHONPATH."""
    old_python_path = _get_python_path(self._version)
    new_python_path = _get_python_path(version)

    old_os_path = _get_os_path(self._version)
    new_os_path = _get_os_path(version)

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

    tf_version = _get_tf_version()
    self._maybe_switch_tpu_version(tf_version)
    self._version = version

  def current_version(self):
    return self._version


def _tensorflow_version(line):
  """Implements the tensorflow_version line magic.

  If no parameter is specified, prints the currently selected and available
  TensorFlow versions. Otherwise, changes the selected version to the given
  version, if it exists.

  Args:
    line: the version parameter or the empty string.
  """
  line = line.strip()

  current_version_name = _instance.current_version().name
  version_names = [v.name for v in _VERSIONS.values()]
  if not line:
    print("Currently selected TF version: {}".format(current_version_name))
    print("Available versions:\n* {}".format("\n* ".join(version_names)))
    return

  _instance.explicitly_set = True
  if line == current_version_name:
    # Nothing to do
    return

  if line not in version_names:
    old_line = line
    if line.startswith("1"):
      line = _VERSIONS["1"].name
    if line.startswith("2"):
      line = _VERSIONS["2"].name
    if line != old_line:
      print(
          textwrap.dedent("""\
        `%tensorflow_version` only switches the major version: {versions}.
        You set: `{old_line}`. This will be interpreted as: `{line}`.

        """.format(
            versions=" or ".join(version_names), old_line=old_line, line=line)))

  if line not in version_names:
    print("Unknown TensorFlow version: {}".format(line))
    print("Currently selected TF version: {}".format(current_version_name))
    print("Available versions:\n * {}".format("\n * ".join(version_names)))
    return

  if "tensorflow" in sys.modules:
    print("TensorFlow is already loaded. Please restart the runtime to "
          "change versions.")
  else:
    version = [v for v in _VERSIONS.values() if v.name == line][0]
    _instance._set_version(version)  # pylint: disable=protected-access
    print("TensorFlow {} selected.".format(line))


def _explicitly_set():
  if _instance is None:
    return False
  return _instance.explicitly_set


def _initialize():
  global _instance
  if _instance is not None:
    raise TypeError("Initialize called multiple times.")
  _instance = _TFVersionManager()


def _register_magics(ip):
  _initialize()
  ip.register_magic_function(
      _tensorflow_version, magic_kind="line", magic_name="tensorflow_version")
