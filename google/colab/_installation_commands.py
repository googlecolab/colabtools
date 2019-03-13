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
"""Installation helpers.

This adds %pip and %conda magic commands, mirroring functionality that was
added in IPython version 7.3.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function


# backport of %pip magic from IPython 7.3; see
# https://github.com/ipython/ipython/pull/11524
def _pip_magic(line):
  """Install a package in the current kernel using pip.

  Usage:
    %pip <command> [options]

  Examples:
    # Install the numpy package
    %pip install numpy

    # Upgrade the pandas library to the most recent release:
    %pip install pandas -U

    # List command help
    %pip help

  Args:
    line : string of arguments to pip command

  Returns:
    None
  """
  ip = get_ipython()  # pylint: disable=undefined-variable
  # Use bare "pip install" rather than "python -m pip install".
  # Colab is set up such that pip does the right thing, and pip install
  # will properly trigger the pip install warning.
  return ip.system('pip {}'.format(line))


def _register_magics(ip):
  ip.register_magic_function(_pip_magic, magic_kind='line', magic_name='pip')
