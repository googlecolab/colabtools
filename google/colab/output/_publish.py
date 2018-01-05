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
"""Provides a bunch of shortcuts to display popular types of content.

This module is nothing by a thin wrapper over IPython.display but it allows
shorter and cleaner code when all we want is to publish common content types.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import hashlib

from IPython import display


def html(content):
  """Publishes given html content into the output."""
  display.display(display.HTML(content))


def css(content=None, url=None):
  """Publishes css content."""
  if url is not None:
    html('<link rel=stylesheet type=text/css href=%r></link>' % url)
  else:
    html('<style>' + content + '</style>')


def javascript(content=None, url=None, script_id=None):
  """Publishes javascript content into the output."""
  if (content is None) == (url is None):
    raise ValueError('exactly one of content and url should be none')
  if url is not None:
    # Note: display.javascript will try to download script from python
    # which is very rarely useful.
    html('<script src=%r></script>' % url)
    return
  if not script_id and 'sourceURL=' not in content:
    script_id = 'js_' + hashlib.md5(content.encode('utf8')).hexdigest()[:10]

  if script_id:
    content += '\n//# sourceURL=%s' % script_id
  display.display(display.Javascript(content))
