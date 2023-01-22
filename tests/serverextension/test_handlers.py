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
"""Tests for the google.colab._serverextension._handlers package."""

import json
import logging
import subprocess
import types
from unittest import mock

from google.colab import _serverextension
from google.colab._serverextension import _handlers
import psutil
from tornado import testing
from tornado import web


_GPU_USAGE = {'usage': 841, 'limit': 4035}
_KERNEL_PID_MAP = {
    '3a7c6914-ce88-4ae8-a37a-9ecf7a21bbef': 1,
    'cfb901b0-c55a-4536-94f8-4d9357265a7a': 2,
}


def fake_check_output(cmdline):
  output = ''
  if cmdline[0] == '/bin/ps':
    pids = _KERNEL_PID_MAP.values()
    output = f'{pids[0]}  135180\n{pids[1]}  143736\n'
  elif 'nvidia-smi' in cmdline:
    output = f"{_GPU_USAGE['usage']}, {_GPU_USAGE['limit']}\n"
  return output.encode()


class FakeNotebookServer:

  def __init__(self, app):
    self.web_app = app
    self.log = logging.getLogger('fake_notebook_server_logger')


class FakeKernelManager:
  """Provides methods faking an IPython MultiKernelManager."""

  def list_kernel_ids(self):
    return _KERNEL_PID_MAP.keys()

  def get_kernel(self, kernel_id):
    return types.SimpleNamespace(
        kernel=types.SimpleNamespace(pid=_KERNEL_PID_MAP[kernel_id])
    )


class ColabResourcesHandlerTest(testing.AsyncHTTPTestCase):
  """Tests for ChunkedFileDownloadHandler."""

  def setUp(self):
    super().setUp()
    mock_check_output = mock.patch.object(
        subprocess, 'check_output', side_effect=fake_check_output
    )
    mock_check_output.start()
    self.addCleanup(mock_check_output.stop)

  def fetch_json(self, path):
    response = self.fetch(path)
    self.assertEqual(response.code, 200)
    body = response.body
    xssi_prefix = _handlers._XSSI_PREFIX  # pylint: disable=protected-access
    self.assertEqual(body[: len(xssi_prefix)].decode(), xssi_prefix)
    return json.loads(body[len(xssi_prefix) :])

  def get_app(self):
    """Setup code required by testing.AsyncHTTP[S]TestCase."""
    settings = {
        'base_url': '/',
        'kernel_manager': FakeKernelManager(),
    }
    app = web.Application([], **settings)
    nb_server_app = FakeNotebookServer(app)
    _serverextension.load_jupyter_server_extension(nb_server_app)
    return app

  def testColabResources(self):
    json_response = self.fetch_json('/api/colab/resources')
    self.assertGreater(json_response['ram']['limit'], 0)

  def testColabResourcesFakeRam(self):
    json_response = self.fetch_json('/api/colab/resources')
    for kernel_id in _KERNEL_PID_MAP:
      self.assertEqual(json_response['ram']['kernels'][kernel_id], 1 << 29)

  def testColabResourcesFakeGPU(self):
    json_response = self.fetch_json('/api/colab/resources')
    self.assertEqual(
        json_response['gpu']['usage'], _GPU_USAGE['usage'] * 1024 * 1024
    )
    self.assertEqual(
        json_response['gpu']['limit'], _GPU_USAGE['limit'] * 1024 * 1024
    )

  def testColabResourcesFakeDisk(self):
    disk_usage = psutil._common.sdiskusage(  # pylint: disable=protected-access
        total=10, used=1, free=9, percent=10
    )

    with mock.patch.object(psutil, 'disk_usage', return_value=disk_usage):
      json_response = self.fetch_json('/api/colab/resources')
    self.assertEqual(json_response['disk']['usage'], 40 << 30)
    self.assertEqual(json_response['disk']['limit'], 120 << 30)
