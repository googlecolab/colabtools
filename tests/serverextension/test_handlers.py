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
import subprocess
import sys
import tempfile

from distutils import spawn

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


class FakeUsage(object):
  """Provides methods that fake memory usage shell invocations."""
  kernel_ids = [
      '3a7c6914-ce88-4ae8-a37a-9ecf7a21bbef',
      'cfb901b0-c55a-4536-94f8-4d9357265a7a'
  ]

  usage = [135180, 143736]

  gpu_usage = {'usage': 841, 'limit': 4035}

  _ps_output = """
{} /usr/bin/python3 -m ipykernel_launcher -f /content/.local/share/jupyter/runtime/kernel-{}.json
{} /usr/bin/python -m ipykernel_launcher -f /content/.local/share/jupyter/runtime/kernel-{}.json
""".format(usage[0], kernel_ids[0], usage[1], kernel_ids[1])

  _nvidia_smi_output = '{}, {}\n'.format(gpu_usage['usage'], gpu_usage['limit'])

  @staticmethod
  def fake_check_output(cmdline):
    output = ''
    if cmdline[0] == 'ps':
      output = FakeUsage._ps_output
    elif cmdline[0] == 'nvidia-smi':
      output = FakeUsage._nvidia_smi_output
    if sys.version_info[0] == 3:  # returns bytes in py3, string in py2
      return bytes(output.encode('utf-8'))
    return output


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


class ColabResourcesHandlerTest(testing.AsyncHTTPTestCase):
  """Tests for ChunkedFileDownloadHandler."""

  def get_app(self):
    """Setup code required by testing.AsyncHTTP[S]TestCase."""
    settings = {
        'base_url': '/',
        # The underyling ipaddress library sometimes doesn't think that
        # 127.0.0.1 is a proper loopback device.
        'local_hostnames': ['127.0.0.1'],
    }
    app = web.Application([], **settings)
    nb_server_app = FakeNotebookServer(app)
    _serverextension.load_jupyter_server_extension(nb_server_app)
    return app

  def testColabResources(self):
    response = self.fetch('/api/colab/resources')
    self.assertEqual(response.code, 200)
    # Body is a JSON response.
    json_response = escape.json_decode(
        response.body[len(_handlers._XSSI_PREFIX):])  # pylint: disable=protected-access
    self.assertGreater(json_response['ram']['limit'], 0)

  @mock.patch.object(
      subprocess,
      'check_output',
      # Use canned ps output.
      side_effect=FakeUsage.fake_check_output,
  )
  def testColabResourcesFakeRam(self, mock_check_output):
    response = self.fetch('/api/colab/resources')
    self.assertEqual(response.code, 200)
    # Body is a JSON response.
    json_response = escape.json_decode(
        response.body[len(_handlers._XSSI_PREFIX):])  # pylint: disable=protected-access
    self.assertEqual(json_response['ram']['kernels'][FakeUsage.kernel_ids[0]],
                     FakeUsage.usage[0] * 1024)
    self.assertEqual(json_response['ram']['kernels'][FakeUsage.kernel_ids[1]],
                     FakeUsage.usage[1] * 1024)

  @mock.patch.object(
      spawn,
      'find_executable',
      # Pretend there is nvidia-smi.
      return_value=True)
  @mock.patch.object(
      subprocess,
      'check_output',
      # Use canned nvidia-smi output.
      side_effect=FakeUsage.fake_check_output,
  )
  def testColabResourcesFakeGPU(self, mock_check_output, mock_find_executable):
    response = self.fetch('/api/colab/resources')
    self.assertEqual(response.code, 200)
    # Body is a JSON response.
    json_response = escape.json_decode(
        response.body[len(_handlers._XSSI_PREFIX):])  # pylint: disable=protected-access
    self.assertEqual(json_response['gpu']['usage'],
                     FakeUsage.gpu_usage['usage'] * 1024 * 1024)
    self.assertEqual(json_response['gpu']['limit'],
                     FakeUsage.gpu_usage['limit'] * 1024 * 1024)
