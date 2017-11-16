"""Colab-specific messaging helpers."""

import time
import uuid

from ipykernel import kernelapp
import zmq
from google.colab import errors

_NOT_READY = object()


class MessageError(errors.Error):
  """Thrown on error response from frontend."""


def _read_next_input_message():
  """Reads the next message from stdin_socket.

  Returns:
    _NOT_READY if input is not available.
  """
  kernel = kernelapp.IPKernelApp.instance().kernel
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


def send_request(request_type, request_body, parent=None):
  """Sends the given message to the frontend."""

  instance = kernelapp.IPKernelApp.instance()

  request_id = str(uuid.uuid4())

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

  Args:
    request_type: type of request being made
    request: Jsonable object to send to front end as the request.
    timeout_sec: max number of seconds to block, None, for no timeout.
    parent: Parent message, for routing.
  Returns:
    Reply by front end (Json'able object), or None if the timeout occurs.
  """
  request_id = send_request(request_type, request, parent=parent)
  return read_reply_from_input(request_id, timeout_sec)
