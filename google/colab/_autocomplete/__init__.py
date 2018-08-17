# Copyright 2017 Google Inc.
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
"""Colabs _autocomplete package."""
from __future__ import absolute_import

import IPython

from google.colab._autocomplete import _dictionary
from google.colab._autocomplete import _splitter


def enable():
  ip = IPython.get_ipython()

  _dictionary.enable()
  _splitter.enable(ip)
