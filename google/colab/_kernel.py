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

import inspect
import warnings

from google.colab import _shell
from google.colab import _shell_customizations
from ipykernel import ipkernel
from ipykernel import jsonutil
from IPython.utils import tokenutil

_AWAITABLE_MESSAGE: str = (
    'For consistency across implementations, it is recommended that'
    ' `{func_name}` either be a coroutine function (`async def`) or return an'
    ' awaitable object (like an `asyncio.Future`). It might become a'
    ' requirement in the future. Coroutine functions and awaitables have been'
    ' supported since ipykernel 6.0 (2021). {target} does not seem to return an'
    ' awaitable'
)


class Kernel(ipkernel.IPythonKernel):
  """Kernel with additional Colab-specific features."""

  def _shell_class_default(self):
    return _shell.Shell

  def do_inspect(self, code, cursor_pos, detail_level=0, *args, **kwargs):
    name = tokenutil.token_at_cursor(code, cursor_pos)
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

  async def complete_request(self, stream, ident, parent):
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
      if inspect.isawaitable(matches):
        matches = await matches
      else:
        warnings.warn(
            _AWAITABLE_MESSAGE.format(
                func_name='do_complete', target=self.do_complete
            ),
            PendingDeprecationWarning,
            stacklevel=1,
        )
      if (
          parent.get('metadata', {})
          .get('colab_options', {})
          .get('include_colab_metadata')
      ):
        # If we're fetching additional metadata on each item, we want to
        # restrict the number of items. We also want to signal that not all
        # matches were included.
        #
        # Note that 100 is an arbitrarily chosen bound for the number of
        # completions to return.
        matches_incomplete = len(matches.get('matches', [])) > 100
        if matches_incomplete:
          matches['matches'] = matches['matches'][:100]
        matches['metadata'] = {
            'colab_types_experimental': (
                _shell_customizations.compute_completion_metadata(
                    self.shell, matches['matches']
                )
            ),
            'matches_incomplete': matches_incomplete,
        }
      matches = jsonutil.json_clean(matches)
    except BaseException as e:  # pylint: disable=broad-except
      # TODO: Return an error here and ensure it's threaded through
      # to the completion failure dialog.
      self.log.info('Error caught during completion: %s', e)
      matches = '{"status":"ok"}'

    self.session.send(stream, 'complete_reply', matches, parent, ident)

  async def inspect_request(self, stream, ident, parent):
    try:
      await super().inspect_request(stream, ident, parent)
    except BaseException as e:  # pylint: disable=broad-except
      # TODO: Consider returning an error here.
      self.log.warning('Error caught during object inspection: %s', e)
      reply_content = '{"status":"ok","found":false}'
      msg = self.session.send(
          stream, 'inspect_reply', reply_content, parent, ident
      )
      self.log.debug('%s', msg)


def _to_primitive(o):
  if isinstance(o, str):
    return o
  if isinstance(o, (int, float, bool, bytes, type(None))):
    return o
  return str(o)
