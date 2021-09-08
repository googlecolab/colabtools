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
"""Support for custom output areas in colab."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import contextlib
import six
from google.colab.output import _js_builder

_jsapi = _js_builder.Js('google.colab')


def _set_output_area(selector):
  if isinstance(selector, six.string_types):
    element = _js_builder.Js('document').querySelector(selector)
  else:
    element = selector
  _jsapi.output.setActiveOutputArea(element)


@contextlib.contextmanager
def redirect_to_element(selector):
  """Will redirect all output to a given element.

  Args:
     selector: either a javascript query selector, or
     Js expression.

  Yields:
    context where the output is redirected
  """
  old_area = _jsapi.output.getActiveOutputArea()
  _set_output_area(selector)
  try:
    yield
  finally:
    _set_output_area(old_area)


@contextlib.contextmanager
def to_header_area():
  """Will redirect output to a header."""
  with redirect_to_element('#output-header') as s:
    yield s


@contextlib.contextmanager
def to_footer_area():
  """Will redirect output to a footer."""
  with redirect_to_element('#output-footer') as s:
    yield s


@contextlib.contextmanager
def to_default_area():
  """Restores output to output into default area."""
  with redirect_to_element(_jsapi.output.getDefaultOutputArea()) as s:
    yield s
