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
"""Tests for the google.colab._handlers package."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import logging
import os
import shutil
import tempfile

from notebook.services.contents import filemanager

from tornado import escape
from tornado import httpclient
from tornado import testing
from tornado import web

from google.colab import _serverextension
from google.colab._serverextension import _handlers

#  pylint:disable=g-import-not-at-top
try:
  from unittest import mock
except ImportError:
  import mock
#  pylint:enable=g-import-not-at-top


class FakeNotebookServer(object):

  def __init__(self, app):
    self.web_app = app
    self.log = logging.getLogger('fake_notebook_server_logger')


class ChunkCapturer(object):

  def __init__(self):
    self.num_chunks_received = 0
    self.content = b''

  def append_chunk(self, chunk):
    self.num_chunks_received += 1
    self.content += chunk


class ChunkedFileDownloadHandlerTest(testing.AsyncHTTPTestCase):
  """Tests for ChunkedFileDownloadHandler."""

  def get_app(self):
    """Setup code required by testing.AsyncHTTP[S]TestCase."""
    self.temp_dir = tempfile.mkdtemp()
    settings = {
        'base_url':
            '/',
        # The underyling ipaddress library sometimes doesn't think that
        # 127.0.0.1 is a proper loopback device.
        'local_hostnames': ['127.0.0.1'],
        'contents_manager':
            filemanager.FileContentsManager(root_dir=self.temp_dir),
    }
    app = web.Application([], **settings)

    nb_server_app = FakeNotebookServer(app)
    _serverextension.load_jupyter_server_extension(nb_server_app)

    return app

  def tearDown(self):
    super(ChunkedFileDownloadHandlerTest, self).tearDown()
    shutil.rmtree(self.temp_dir)

  def testNonExistentFile(self):
    response = self.fetch('/api/chunked-contents/in/some/dir/foo.py')
    self.assertEqual(response.code, 404)
    # Body is a JSON response.
    json_response = escape.json_decode(response.body)
    self.assertIn('No such file or directory', json_response['message'])

  def testExistingDirectory(self):
    os.makedirs(os.path.join(self.temp_dir, 'some/existing/dir'))
    response = self.fetch('/api/chunked-contents/some/existing/dir')
    self.assertEqual(response.code, 400)
    # Body is a JSON response.
    json_response = escape.json_decode(response.body)
    self.assertIn('is a directory, not a file', json_response['message'])

  def testExistingFile(self):
    file_dir = os.path.join(self.temp_dir, 'some/existing/dir')
    os.makedirs(file_dir)
    with open(os.path.join(file_dir, 'foo.txt'), 'wb') as f:
      f.write(b'Some content')

    response = self.fetch('/api/chunked-contents/some/existing/dir/foo.txt')
    self.assertEqual(200, response.code)
    # Body is the raw file contents.
    self.assertEqual(b'Some content', response.body)
    self.assertEqual('chunked', response.headers['Transfer-Encoding'])
    self.assertEqual('text/plain', response.headers['Content-Type'])
    self.assertEqual(len(b'Some content'), int(response.headers['X-File-Size']))

  @mock.patch.object(
      _handlers.ChunkedFileDownloadHandler,
      'CHUNK_SIZE',
      new_callable=mock.PropertyMock,
      # Overwrite the chunk size to a small default.
      return_value=1)
  def testExistingFileReturnsMultipleChunks(self, mock_chunk_size):
    file_dir = os.path.join(self.temp_dir, 'some/existing/dir')
    os.makedirs(file_dir)
    with open(os.path.join(file_dir, 'foo.txt'), 'wb') as f:
      f.write(b'Some content')

    capturer = ChunkCapturer()
    url = self.get_url('/api/chunked-contents/some/existing/dir/foo.txt')
    request = httpclient.HTTPRequest(
        url=url,
        # Setting streaming_callback causes the supplied function to be invoked
        # every time a chunk of the response is received. When provided, the
        # "body" attribute of the response is not set.
        streaming_callback=capturer.append_chunk)

    response = self.io_loop.run_sync(lambda: self.http_client.fetch(request))
    self.assertEqual(response.code, 200)
    self.assertEqual(len(b'Some content'), capturer.num_chunks_received)
    self.assertEqual(b'Some content', capturer.content)
    self.assertEqual('chunked', response.headers['Transfer-Encoding'])
    self.assertEqual('text/plain', response.headers['Content-Type'])
    self.assertEqual(len(b'Some content'), int(response.headers['X-File-Size']))

  def testDoesNotAllowRequestsOutsideOfRootDir(self):
    # Based on existing tests:
    # https://github.com/jupyter/notebook/blob/f5fa0c180e92d35b4cbfa1cc20b41e9d1d9dfabe/notebook/services/contents/tests/test_manager.py#L173
    with open(os.path.join(self.temp_dir, '..', 'foo'), 'w') as f:
      f.write('foo')
    with open(os.path.join(self.temp_dir, '..', 'bar'), 'w') as f:
      f.write('bar')

    response = self.fetch('/api/chunked-contents/../foo')
    self.assertEqual(404, response.code)
    response = self.fetch('/api/chunked-contents/foo/../../../bar')
    self.assertEqual(404, response.code)
    response = self.fetch('/api/chunked-contents/foo/../../bar')
    self.assertEqual(404, response.code)
