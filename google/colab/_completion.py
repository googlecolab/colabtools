# Copyright 2026 Google Inc.
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
"""Helpers for shaping `complete_reply` payloads.

Kept free of IPython and ipykernel imports so it can be unit tested against an
interpreter that does not provide the IPython 8.x-specific modules.
"""

import re

# The dotted expression immediately preceding the cursor, e.g. the `a.b` in
# `print(a.b.pre`. Used to restore fully-qualified attribute completions.
_DOTTED_PREFIX = re.compile(
    r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$'
)

# ipykernel's `complete_reply` metadata key for IPython `Completion` entries.
JUPYTER_EXPERIMENTAL_KEY = '_jupyter_types_experimental'


def requalify_attribute_matches(code, reply):
  """Rewrites relative attribute completions back to fully-qualified names.

  IPython 8.x returns `Completion` objects: for `s.cap` the
  match text is `.capitalize`, replacing `code[cursor_start:cursor_end]` where
  `cursor_start` is the offset of the `.`. Pre-8.x returned `s.capitalize` with
  `cursor_start` at the start of the whole expression.

  Colab's contract with the frontend, and `compute_completion_metadata`'s
  `object_inspect` lookups, both assume the fully-qualified form: `.capitalize`
  resolves to nothing, so the completion popup silently loses its type and
  signature detail. This restores the pre-8.x shape.

  Only applies when the reply is unambiguously an attribute completion (every
  match begins with `.`), so other matchers (keyword arguments, dict keys,
  magics, file paths) are left untouched.

  Args:
    code: The full code buffer that was completed.
    reply: A `do_complete` reply dict. Mutated in place.

  Returns:
    The same `reply` dict.
  """
  matches = reply.get('matches')
  cursor_start = reply.get('cursor_start')
  if not matches or cursor_start is None:
    return reply
  if not all(match.startswith('.') for match in matches):
    return reply

  prefix_match = _DOTTED_PREFIX.search(code[:cursor_start])
  if not prefix_match:
    return reply
  prefix = prefix_match.group()

  reply['matches'] = [prefix + match for match in matches]
  reply['cursor_start'] = cursor_start - len(prefix)

  # Keep ipykernel's parallel `complete_reply` metadata consistent with the
  # rewrite; otherwise its offsets disagree with the ones just widened.
  experimental = reply.get('metadata', {}).get(JUPYTER_EXPERIMENTAL_KEY)
  for entry in experimental or ():
    if entry.get('text', '').startswith('.'):
      entry['text'] = prefix + entry['text']
      entry['start'] = reply['cursor_start']

  return reply
