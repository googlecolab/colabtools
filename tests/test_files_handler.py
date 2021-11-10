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
"""Tests for the google.colab._files_handler package."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import logging
import os
import shutil
import tempfile

from six.moves import http_client

from tornado import testing
from tornado import web

from google.colab import _files_handler


class FakeNotebookServer(object):

  def __init__(self, app):
    self.web_app = app
    self.log = logging.getLogger('fake_notebook_server_logger')


class ColabAuthenticatedFileHandler(testing.AsyncHTTPTestCase):
  """Tests for ColabAuthenticatedFileHandler."""

  def get_app(self):
    """Setup code required by testing.AsyncHTTP[S]TestCase."""
    self.temp_dir = tempfile.mkdtemp()
    settings = {
        'base_url': '/',
        # The underlying ipaddress library sometimes doesn't think that
        # 127.0.0.1 is a proper loopback device.
        'local_hostnames': ['127.0.0.1'],
    }
    app = web.Application([], **settings)
    app.add_handlers('.*$', [
        ('/files/(.*)', _files_handler.ColabAuthenticatedFileHandler, {
            'path': self.temp_dir + '/'
        }),
    ])

    return app

  def tearDown(self):
    super(ColabAuthenticatedFileHandler, self).tearDown()
    shutil.rmtree(self.temp_dir)

  def testNonExistentFile(self):
    response = self.fetch('/files/in/some/dir/foo.py')
    self.assertEqual(http_client.NOT_FOUND, response.code)

  def testExistingDirectory(self):
    os.makedirs(os.path.join(self.temp_dir, 'some/existing/dir'))
    response = self.fetch('/files/some/existing/dir')
    self.assertEqual(http_client.FORBIDDEN, response.code)

  def testExistingFile(self):
    file_dir = os.path.join(self.temp_dir, 'some/existing/dir')
    os.makedirs(file_dir)
    with open(os.path.join(file_dir, 'foo.txt'), 'wb') as f:
      f.write(b'Some content')

    response = self.fetch('/files/some/existing/dir/foo.txt')
    self.assertEqual(http_client.OK, response.code)
    # Body is the raw file contents.
    self.assertEqual(b'Some content', response.body)
    self.assertEqual(len(b'Some content'), int(response.headers['X-File-Size']))
    self.assertIn('text/plain', response.headers['Content-Type'])

  def testDoesNotAllowRequestsOutsideOfRootDir(self):
    # Based on existing tests:
    # https://github.com/jupyter/notebook/blob/f5fa0c180e92d35b4cbfa1cc20b41e9d1d9dfabe/notebook/services/contents/tests/test_manager.py#L173
    with open(os.path.join(self.temp_dir, '..', 'foo'), 'w') as f:
      f.write('foo')
    with open(os.path.join(self.temp_dir, '..', 'bar'), 'w') as f:
      f.write('bar')

    response = self.fetch('/files/../foo')
    self.assertEqual(http_client.FORBIDDEN, response.code)
    response = self.fetch('/files/foo/../../../bar')
    self.assertEqual(http_client.FORBIDDEN, response.code)
    response = self.fetch('/files/foo/../../bar')
    self.assertEqual(http_client.FORBIDDEN, response.code)
