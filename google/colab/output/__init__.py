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
"""Colabs output package."""
# pylint: disable=g-multiple-import
from google.colab.output._area import redirect_to_element, to_default_area, to_footer_area, to_header_area
from google.colab.output._js import eval_js, register_callback
from google.colab.output._tags import clear, temporary, use_tags
from google.colab.output._util import serve_kernel_port_as_iframe, serve_kernel_port_as_window
from google.colab.output._widgets import enable_custom_widget_manager, disable_custom_widget_manager
