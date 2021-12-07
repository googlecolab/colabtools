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
"""Common error types used across Colab python functions."""

from __future__ import absolute_import as _
from __future__ import division as _
from __future__ import print_function as _


class Error(Exception):
  """Base class for all Colab errors."""


class AuthorizationError(Error):
  """Authorization-related failures."""


class WidgetException(Exception):  # pylint: disable=g-bad-exception-name
  """colab.widgets failures."""
