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
"""Colab-specific kernel customizations."""

from ipykernel import ipkernel
from ipykernel.jsonutil import json_clean
from IPython.utils.tokenutil import token_at_cursor
import six
from google.colab import _shell
from google.colab import _shell_customizations


class Kernel(ipkernel.IPythonKernel):
  """Kernel with additional Colab-specific features."""

  def _shell_class_default(self):
    return _shell.Shell

  def do_inspect(self, code, cursor_pos, detail_level=0):
    name = token_at_cursor(code, cursor_pos)
    info = self.shell.object_inspect(name)

    data = {}
    if info['found']:
      info_text = self.shell.object_inspect_text(
          name,
          detail_level=detail_level,
      )
      data['text/plain'] = info_text
      # Provide the structured inspection information to allow the frontend to
      # format as desired.
      argspec = info.get('argspec')
      if argspec:
        defaults = argspec.get('defaults')
        if defaults:
          argspec['defaults'] = [_to_primitive(x) for x in defaults]
      data['application/json'] = info

    reply_content = {
        'status': 'ok',
        'data': data,
        'metadata': {},
        'found': info['found'],
    }

    return reply_content

  def complete_request(self, stream, ident, parent):
    """Colab-specific complete_request handler.

    Overrides the default to allow providing additional metadata in the
    response.

    Args:
      stream: Shell stream to send the reply on.
      ident: Identity of the requester.
      parent: Parent request message.
    """

    content = parent['content']
    code = content['code']
    cursor_pos = content['cursor_pos']

    matches = self.do_complete(code, cursor_pos)
    if parent.get('metadata', {}).get('colab_options',
                                      {}).get('include_colab_metadata'):
      matches['metadata'] = {
          'colab_types_experimental':
              _shell_customizations.compute_completion_metadata(
                  self.shell, matches['matches']),
      }
    matches = json_clean(matches)

    self.session.send(stream, 'complete_reply', matches, parent, ident)


def _to_primitive(o):
  if isinstance(o, six.string_types):
    return o
  if isinstance(o, (int, float, bool, bytes, type(None))):
    return o
  return str(o)
