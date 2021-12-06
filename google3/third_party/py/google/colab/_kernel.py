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

from google.colab import _shell
from google.colab import _shell_customizations
from ipykernel import ipkernel
from ipykernel.jsonutil import json_clean
from IPython.utils.tokenutil import token_at_cursor
import six
import zmq


def set_unlimited_hwm():
  ctx = zmq.Context.instance()
  ctx.sockopts = {zmq.RCVHWM: 0, zmq.SNDHWM: 0}


# ZMQ sockets should never silently drop messages. HWM means
# 'high water mark' and is the number of messages after which
# ZMQ will silently drop messages on PUB/SUB sockets.
#
# To adjust the default HWM of all IPython sockets, we set the sockopts field
# of the zmq.sugar.context.Context object during IPython kernel startup.
# (Socket options must be set prior to connection.)
set_unlimited_hwm()


class Kernel(ipkernel.IPythonKernel):
  """Kernel with additional Colab-specific features."""

  def _shell_class_default(self):
    return _shell.Shell

  def do_inspect(self, code, cursor_pos, detail_level=0):
    name = token_at_cursor(code, cursor_pos)
    info = self.shell.object_inspect(name)

    data = {}
    if info['found']:
      # Provide the structured inspection information to allow the frontend to
      # format as desired.
      argspec = info.get('argspec')
      if argspec:
        defaults = argspec.get('defaults')
        if defaults:
          argspec['defaults'] = [_to_primitive(x) for x in defaults]
        annotations = argspec.get('annotations')
        if annotations:
          for key, value in annotations.items():
            annotations[key] = _to_primitive(value)
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
    try:
      content = parent['content']
      code = content['code']
      cursor_pos = content['cursor_pos']

      matches = self.do_complete(code, cursor_pos)
      if parent.get('metadata', {}).get('colab_options',
                                        {}).get('include_colab_metadata'):
        # If we're fetching additional metadata on each item, we want to
        # restrict the number of items. We also want to signal that not all
        # matches were included.
        #
        # Note that 100 is an arbitrarily chosen bound for the number of
        # completions to return.
        matches_incomplete = len(matches['matches']) > 100
        if matches_incomplete:
          matches['matches'] = matches['matches'][:100]
        matches['metadata'] = {
            'colab_types_experimental':
                _shell_customizations.compute_completion_metadata(
                    self.shell, matches['matches']),
            'matches_incomplete':
                matches_incomplete,
        }
      matches = json_clean(matches)
    except BaseException as e:  # pylint: disable=broad-except
      # TODO(b/124400682): Return an error here and ensure it's threaded through
      # to the completion failure dialog.
      self.log.info('Error caught during completion: %s', e)
      matches = '{"status":"ok"}'

    self.session.send(stream, 'complete_reply', matches, parent, ident)

  def inspect_request(self, stream, ident, parent):
    # TODO(b/147296819): Consider reverting to a `super()` call here once we
    # support async.
    try:
      content = parent['content']
      reply_content = self.do_inspect(content['code'], content['cursor_pos'],
                                      content.get('detail_level', 0))
      reply_content = json_clean(reply_content)
    except BaseException as e:  # pylint: disable=broad-except
      # TODO(b/124400682): Consider returning an error here.
      self.log.info('Error caught during object inspection: %s', e)
      reply_content = '{"status":"ok","found":false}'
    msg = self.session.send(stream, 'inspect_reply', reply_content, parent,
                            ident)
    self.log.debug('%s', msg)


def _to_primitive(o):
  if isinstance(o, six.string_types):
    return o
  if isinstance(o, (int, float, bool, bytes, type(None))):
    return o
  return str(o)
