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
"""This module provides support for tagging and selectively deleting outputs."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import contextlib
import sys
import threading
import uuid

from google.colab import _ipython as ipython
import IPython
from IPython import display
import six


def _add_or_remove_tags(tags_to_add=(), tags_to_remove=()):
  """Adds or removes tags from the frontend."""
  # Clear tags when this cell is done.
  output_tags = _get_or_create_tags()
  tags_to_add = tuple(tags_to_add)
  tags_to_remove = tuple(tags_to_remove)

  output_tags.update(tags_to_add)
  output_tags.difference_update(tags_to_remove)

  sys.stdout.flush()
  sys.stderr.flush()

  metadata = {
      'outputarea': {
          'nodisplay': True,
          'add_tags': tags_to_add,
          'remove_tags': tags_to_remove
      }
  }

  if ipython.in_ipython():
    if IPython.version_info[0] > 2:
      display.publish_display_data({}, metadata=metadata)
    else:
      display.publish_display_data('display', {}, metadata=metadata)

  return output_tags


def _convert_string_to_list(v):
  return [v] if isinstance(v, six.string_types) else v


# Thread local storage for tags
_tls = threading.local()


def _get_or_create_tags(create=True):
  if not hasattr(_tls, 'tags') and create:
    _tls.tags = set()
  return getattr(_tls, 'tags', None)


def reset_tags():
  """Resets output tags in the runtime.

  This function is an escape hatch in case runtime ends up in
  inconsistent state between frontend (where tags are cell local)
  and runtime (which mantains global state).
  """
  if hasattr(_tls, 'tags'):
    del _tls.tags


def get_active_tags():
  return set(_get_or_create_tags(create=False) or ())


@contextlib.contextmanager
def use_tags(tags, append=True):
  """Will add `tags` to all outputs within this context.

  Tags allow user to mark output (such as one produce by print statments,
  images and any other output ), and later delete a subset of it
  that have given set of tags.

  Note 1: the set of tags will be restored even if underlying code
  throws exception.

  Note 2: This function is not thread safe.
  If this function is accessed from non-ui thread, it might lead to
  racing behaviors unless special care is taken of clean ups, otherwise
  tags added from different threads will interfere with each other on frontend.

  Note 3: Using this function outside of context manager is not supported and
  is undefined behavior. Specifically if __exit__ is not called across
  single run_cell, this might lead to broken output in future cell runs.

  Args:
    tags: one or more tags to attach to outputs within this context
    append: if true, the set of tag will be added to currently
    active, otherwise it will replace the set.

  Yields:
    set of current tags.
  """
  tags = _convert_string_to_list(tags)
  try:
    current_tags = set(_get_or_create_tags())
    # remove all tags which were not in the current_tags
    added_tags = set(tags).difference(current_tags)
    remove_tags = [] if append else set(current_tags).difference(tags)
    tags = _add_or_remove_tags(
        tags_to_add=added_tags, tags_to_remove=remove_tags)
    yield tags
  finally:
    _add_or_remove_tags(tags_to_add=remove_tags, tags_to_remove=added_tags)


def clear(wait=False, output_tags=()):
  """Clears all output marked with a superset of a given output_tags.

  For example:
    from google.colab import output
    with output.use_tag('conversation'):
      with output.use_tag('introduction'):
         print('Hello')
      print('Bye')

    # This will remove 'hello' from the output
    output.clear(output_tags='introduction')
    # This will remove bye from the output
    output.clear(output_tags='conversation')

  If wait is true, the operation will be deferred
  until next output statement. For example:

    print("hello")
    output.clear(wait=True)
    time.sleep(10)
    print("bye")

  will have "Hello" printed for 10 seconds, then replace it with "bye".

  Args:
    wait: whether to wait until the next output before clearing output.

    output_tags: string or iterable over strings. If provided, only
    outputs that are marked with superset of output_tags will be cleared.
  """
  if not isinstance(wait, bool):
    raise ValueError('wait must be a boolean value')

  output_tags = _convert_string_to_list(output_tags)
  content = dict(wait=wait, output_tags=tuple(output_tags))

  # In contrast with ipython we don't send any extraneous symbols to
  # stdin/stdout.
  sys.stdout.flush()
  sys.stderr.flush()

  ip = IPython.get_ipython()
  if not ip or not hasattr(ip, 'kernel'):
    return

  if not hasattr(ip.kernel, 'shell'):
    return
  display_pub = ip.kernel.shell.display_pub
  if not hasattr(display_pub, 'pub_socket'):
    return
  session = ip.kernel.session
  session.send(
      display_pub.pub_socket,
      u'clear_output',
      content,
      parent=display_pub.parent_header,
      ident=display_pub.topic)


@contextlib.contextmanager
def temporary():
  """Outputs produced within this context will be cleared upon exiting.

  Note: if context throws exception no output will be cleared.

  Yields:
    None
  """
  temptag = str(uuid.uuid4())
  with use_tags(temptag):
    yield temptag
  clear(output_tags=temptag)
