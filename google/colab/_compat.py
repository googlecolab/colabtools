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
"""Colab Python2/Python3 compatibility helpers."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import six


def as_binary(bytes_or_str):
  """Convert a bytes or unicode object to (UTF8) bytes."""
  if isinstance(bytes_or_str, six.binary_type):
    return bytes_or_str
  if isinstance(bytes_or_str, six.text_type):
    return bytes_or_str.encode('utf8')
  raise ValueError('Unknown type: {}'.format(type(bytes_or_str)))
