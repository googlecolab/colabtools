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

Provides a %tensorflow_version line magic which is a noop.
"""

import textwrap


def _tensorflow_version(line):
  """Implements the tensorflow_version line magic.

  If no parameter is specified, prints the currently selected and available
  TensorFlow versions. Otherwise, changes the selected version to the given
  version, if it exists.

  Args:
    line: the version parameter or the empty string.
  """
  line = line.strip()

  if line.startswith("1"):
    raise ValueError(
        # pylint: disable=line-too-long
        textwrap.dedent("""\
             Tensorflow 1 is unsupported in Colab.
    
             Your notebook should be updated to use Tensorflow 2.
             See the guide at https://www.tensorflow.org/guide/migrate#migrate-from-tensorflow-1x-to-tensorflow-2."""
                       ))

  print(
      "Colab only includes TensorFlow 2.x; %tensorflow_version has no effect.")


def _register_magics(ip):
  ip.register_magic_function(
      _tensorflow_version, magic_kind="line", magic_name="tensorflow_version")
