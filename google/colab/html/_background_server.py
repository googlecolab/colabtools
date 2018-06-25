# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""WSGI server utilities to run in thread. WSGI chosen for easier interop."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import socket
import threading
import wsgiref.simple_server
import portpicker


def _build_server(started, stopped, stopping, timeout):
  """Closure to build the server function to be passed to the thread.

  Args:
    started: Threading event to notify when started.
    stopped: Threading event to notify when stopped.
    stopping: Threading event to notify when stopping.
    timeout: Http timeout in seconds.
  Returns:
    A function that function that takes a port and WSGI app and notifies
      about its status via the threading events provided.
  """

  def server(port, wsgi_app):
    """Serve a WSGI application until stopped.

    Args:
      port: Port number to serve on.
      wsgi_app: WSGI application to serve.
    """
    host = ''  # Bind to all.
    try:
      httpd = wsgiref.simple_server.make_server(
          host, port, wsgi_app, handler_class=SilentWSGIRequestHandler)
    except socket.error:
      # Try IPv6
      httpd = wsgiref.simple_server.make_server(
          host,
          port,
          wsgi_app,
          server_class=_WSGIServerIPv6,
          handler_class=SilentWSGIRequestHandler)
    started.set()
    httpd.timeout = timeout
    while not stopping.is_set():
      httpd.handle_request()
    stopped.set()

  return server


class SilentWSGIRequestHandler(wsgiref.simple_server.WSGIRequestHandler):
  """WSGIRequestHandler that generates no logging output."""

  def log_message(self, format, *args):  # pylint: disable=redefined-builtin
    pass


class _WSGIServerIPv6(wsgiref.simple_server.WSGIServer):
  """IPv6 based extension of the simple WSGIServer."""

  address_family = socket.AF_INET6


class _WsgiServer(object):
  """Wsgi server."""

  def __init__(self, wsgi_app):
    """Initialize the WsgiServer.

    Args:
      wsgi_app: WSGI pep-333 application to run.
    """
    self._app = wsgi_app
    self._server_thread = None
    # Threading.Event objects used to communicate about the status
    # of the server running in the background thread.
    # These will be initialized after building the server.
    self._stopped = None
    self._stopping = None

  @property
  def wsgi_app(self):
    """Returns the wsgi app instance."""
    return self._app

  @property
  def port(self):
    """Returns the current port or error if the server is not started.

    Raises:
      RuntimeError: If server has not been started yet.
    Returns:
      The port being used by the server.
    """
    if self._server_thread is None:
      raise RuntimeError('Server not running.')
    return self._port

  def stop(self):
    """Stops the server thread."""
    if self._server_thread is None:
      return
    self._stopping.set()
    self._server_thread = None
    self._stopped.wait()

  def start(self, port=None, timeout=1):
    """Starts a server in a thread using the WSGI application provided.

    Will wait until the thread has started calling with an already serving
    application will simple return.

    Args:
      port: Number of the port to use for the application, will find an open
        port if one is not provided.
      timeout: Http timeout in seconds.
    """
    if self._server_thread is not None:
      return
    started = threading.Event()
    self._stopped = threading.Event()
    self._stopping = threading.Event()

    wsgi_app = self.wsgi_app
    server = _build_server(started, self._stopped, self._stopping, timeout)
    if port is None:
      self._port = portpicker.pick_unused_port()
    else:
      self._port = port
    server_thread = threading.Thread(target=server, args=(self._port, wsgi_app))
    self._server_thread = server_thread

    server_thread.start()
    started.wait()
