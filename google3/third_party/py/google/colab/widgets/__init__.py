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
"""High level widgets for display in the output area.

Many of these widgets allow to output standard channels (e.g. print statements,
or matplotlib) into specific part of the widget, such as individual tab or
grid's cell. This allows to build complex interactive outputs, using libraries
that are not even aware of the widget's existence.
"""
from google.colab.widgets._grid import create_grid
from google.colab.widgets._grid import Grid
from google.colab.widgets._tabbar import TabBar
