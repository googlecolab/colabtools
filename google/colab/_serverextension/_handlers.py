# Copyright 2018 Google Inc.
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
"""Custom Jupyter notebook API handlers."""

import json
import mimetypes
import os

from notebook.base import handlers

import tornado
from tornado import web

from google.colab._serverextension import _resource_monitor

_XSSI_PREFIX = ")]}'\n"


class ChunkedFileDownloadHandler(handlers.APIHandler):
  """API handler that returns the file contents in a streaming HTTP response.

  Note: This is similar to the behavior of the built-in
  notebook.services.contents.handlers.ContentsHandler. The motivation for this
  is when a frontend is downloading a large file. In the built-in
  ContentsHandler, the entire file is read, base-64 encoded, and serialized to
  JSON. The client is then responsible for awaiting the entire JSON response,
  parsing it, and base-64 decoding the contents.

  ChunkedFileDownloadHandler instead uses HTTP chunked streaming to send the
  raw binary contents of the file, avoiding base-64 encoding as well as JSON
  serialization.
  """

  CHUNK_SIZE = 2**20  # 1MB

  @tornado.web.authenticated
  @tornado.gen.coroutine
  def get(self, path=''):
    path = path or ''

    if not self.contents_manager.exists(path):
      raise web.HTTPError(404, u'No such file or directory: {}'.format(path))

    os_path = self.contents_manager._get_os_path(path)  # pylint:disable=protected-access
    if os.path.isdir(os_path):
      raise web.HTTPError(400, u'{} is a directory, not a file'.format(path))

    mimetype = mimetypes.guess_type(os_path)[0] or 'application/octet-stream'
    self.set_header('Content-Type', mimetype)

    size = self._get_file_size(os_path)
    if size:
      # When using a Content-Encoding other than "identity", the Content-Length
      # header must not be specified (https://www.ietf.org/rfc/rfc2616.txt).
      # We set a separate header for clients wishing to obtain progress
      # information.
      self.set_header('X-File-Size', size)

    with self.contents_manager.open(os_path, 'rb') as f:
      bcontent = f.read(self.CHUNK_SIZE)
      while bcontent:
        self.write(bcontent)
        yield self.flush()
        bcontent = f.read(self.CHUNK_SIZE)

    self.finish()

  def _get_file_size(self, path):
    try:
      return os.lstat(path).st_size
    except (ValueError, OSError):
      return None


class ResourceUsageHandler(handlers.APIHandler):
  """Handles requests for memory usage of Colab kernels."""

  @tornado.web.authenticated
  def get(self, *unused_args, **unused_kwargs):
    ram = _resource_monitor.get_ram_usage()
    gpu = _resource_monitor.get_gpu_usage()
    disk = _resource_monitor.get_disk_usage()
    self.set_header('Content-Type', 'application/json')
    self.finish(_XSSI_PREFIX + json.dumps({
        'ram': ram,
        'gpu': gpu,
        'disk': disk
    }))
