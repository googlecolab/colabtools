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
"""Colab import customizations to the IPython runtime."""

from google.colab._import_hooks import _altair
from google.colab._import_hooks import _bokeh
from google.colab._import_hooks import _client_info
from google.colab._import_hooks import _cv2
from google.colab._import_hooks import _generativeai
from google.colab._import_hooks import _pydrive
from google.colab._import_hooks import _pydrive2


def _register_hooks():
  _altair._register_hook()  # pylint:disable=protected-access
  _bokeh._register_hook()  # pylint:disable=protected-access
  _client_info._register_hook()  # pylint:disable=protected-access
  _cv2._register_hook()  # pylint:disable=protected-access
  _generativeai._register_hook()  # pylint:disable=protected-access
  _pydrive._register_hook()  # pylint:disable=protected-access
  _pydrive2._register_hook()  # pylint:disable=protected-access
