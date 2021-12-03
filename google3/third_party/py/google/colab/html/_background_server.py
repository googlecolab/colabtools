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
"""Tornado server running in a background thread."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import threading

import portpicker
import tornado
import tornado.httpserver
import tornado.ioloop
import tornado.web


class _BackgroundServer(object):
  """HTTP server that runs in a background thread."""

  def __init__(self, app):
    """Initialize (but do not start) background server.

    Args:
      app: server application to run.
    """
    self._app = app

    # These will be initialized when starting the server.
    self._port = None
    self._server_thread = None
    self._ioloop = None
    self._server = None

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
    """Stops the server thread.

    Raises:
      RuntimeError: if server is already stopped.
    """
    if self._server_thread is None:
      raise RuntimeError('stop() called on stopped server')

    def shutdown():
      self._server.stop()
      self._ioloop.stop()

    try:
      self._ioloop.add_callback(shutdown)
      self._server_thread.join()
      self._ioloop.close(all_fds=True)
    finally:
      self._server_thread = None

  def start(self, port=None, timeout=1):
    """Starts a server in a thread using the WSGI application provided.

    Will wait until the thread has started calling with an already serving
    application will simple return.

    Args:
      port: Number of the port to use for the application, will find an open
        port if a nonzero port is not provided.
      timeout: Http timeout in seconds. Note that this is only respected under
        tornado v4.

    Raises:
      RuntimeError: if server is already started.
    """
    if self._server_thread is not None:
      raise RuntimeError('start() called on running background server.')

    self._port = port or portpicker.pick_unused_port()

    # Support both internal & external colab (tornado v3 vs. v4)
    # TODO(b/35548011): remove tornado v3 handling
    if tornado.version[0] >= '4':
      kwds = {'idle_connection_timeout': timeout, 'body_timeout': timeout}
    else:
      kwds = {}
    self._server = tornado.httpserver.HTTPServer(self._app, **kwds)
    self._ioloop = tornado.ioloop.IOLoop()

    def start_server(httpd, ioloop, port):
      # TODO(b/147233568): Restrict this to local connections.
      host = ''  # Bind to all
      ioloop.make_current()
      httpd.listen(port=port, address=host)
      ioloop.start()

    self._server_thread = threading.Thread(
        target=start_server,
        kwargs={
            'httpd': self._server,
            'ioloop': self._ioloop,
            'port': self._port
        })
    started = threading.Event()
    self._ioloop.add_callback(started.set)
    self._server_thread.start()
    started.wait()
