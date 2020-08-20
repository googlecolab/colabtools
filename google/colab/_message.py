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
"""Colab-specific messaging helpers."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import time

import zmq

from google.colab import _ipython as ipython
from google.colab import errors

_NOT_READY = object()


class MessageError(errors.Error):
  """Thrown on error response from frontend."""


def _read_next_input_message():
  """Reads the next message from stdin_socket.

  Returns:
    _NOT_READY if input is not available.
  """
  kernel = ipython.get_kernel()
  stdin_socket = kernel.stdin_socket

  reply = None
  try:
    _, reply = kernel.session.recv(stdin_socket, zmq.NOBLOCK)
  except Exception:  # pylint: disable=broad-except
    # We treat invalid messages as empty replies.
    pass
  if reply is None:
    return _NOT_READY

  # We want to return '' even if reply is malformed.
  return reply.get('content', {}).get('value', '')


def _read_stdin_message():
  """Reads a stdin message.

  This discards any colab messaging replies that may arrive on the stdin_socket.

  Returns:
    The input message or None if input is not available.
  """
  while True:
    value = _read_next_input_message()
    if value == _NOT_READY:
      return None

    # Skip any colab responses.
    if isinstance(value, dict) and value.get('type') == 'colab_reply':
      continue

    return value


def read_reply_from_input(message_id, timeout_sec=None):
  """Reads a reply to the message from the stdin channel.

  Any extraneous input or messages received on the stdin channel while waiting
  for the reply are discarded. This blocks until the reply has been
  received.

  Args:
    message_id: the ID of the request for which this is blocking.
    timeout_sec: blocks for that many seconds.

  Returns:
    If a reply of type `colab_reply` for `message_id` is returned before the
    timeout, we return reply['data'] or None.
    If a timeout is provided and no reply is received, we return None.

  Raises:
    MessageError: if a reply is returned to us with an error.
  """
  deadline = None
  if timeout_sec:
    deadline = time.time() + timeout_sec
  while not deadline or time.time() < deadline:
    reply = _read_next_input_message()
    if reply == _NOT_READY or not isinstance(reply, dict):
      time.sleep(0.025)
      continue
    if (reply.get('type') == 'colab_reply' and
        reply.get('colab_msg_id') == message_id):
      if 'error' in reply:
        raise MessageError(reply['error'])
      return reply.get('data', None)

# Global counter for message id.
# Note: this is not thread safe, if we want to make this
# thread sfe we should replace this with thread safe counter
# And add appropriate thread handling logic to read_reply_from_input
_msg_id = 0


def send_request(request_type, request_body, parent=None):
  """Sends the given message to the frontend without waiting for a reply."""

  instance = ipython.get_kernelapp()
  global _msg_id
  _msg_id += 1
  request_id = _msg_id

  metadata = {
      'colab_msg_id': request_id,
      'colab_request_type': request_type,
  }

  content = {
      'request': request_body,
  }

  # If there's no parent message, add in the session header to route to the
  # appropriate frontend.
  if parent is None:
    parent_header = instance.kernel.shell.parent_header
    if parent_header:
      parent = {
          'header': {
              # Only specifying the session if it is not a cell-related message.
              'session': parent_header['header']['session']
          },
      }

  msg = instance.session.msg(
      'colab_request', content=content, metadata=metadata, parent=parent)
  instance.session.send(instance.iopub_socket, msg)

  return request_id


def blocking_request(request_type, request='', timeout_sec=5, parent=None):
  """Calls the front end with a request, and blocks until a reply is received.

  Note: this function is not thread safe, e.g. if two threads
  send blocking_request they will likely race with each other and consume
  each other responses leaving another thread deadlocked.

  Args:
    request_type: type of request being made
    request: Jsonable object to send to front end as the request.
    timeout_sec: max number of seconds to block, None, for no timeout.
    parent: Parent message, for routing.
  Returns:
    Reply by front end (Json'able object), or None if the timeout occurs.
  """
  # If we want this thread safe we can make read_reply_from_input to
  # not discard messages with unknown msg ids as well as making msg_ids globally
  # unique.
  request_id = send_request(request_type, request, parent=parent)
  return read_reply_from_input(request_id, timeout_sec)
