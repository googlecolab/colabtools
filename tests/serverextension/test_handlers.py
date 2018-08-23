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

import collections
import logging
import subprocess
import sys
from distutils import spawn

import psutil

from tornado import escape
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

  pids = [1, 2]

  usage = [135180, 143736]

  gpu_usage = {'usage': 841, 'limit': 4035}

  disk_usage = psutil._common.sdiskusage(  # pylint: disable=protected-access
      total=10, used=1, free=9, percent=10)

  _ps_output = '{}  {}\n{}  {}\n'.format(pids[0], usage[0], pids[1], usage[1])

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


class FakeKernelManager(object):
  """Provides methods faking an IPython MultiKernelManager."""
  _kernel_factory = collections.namedtuple('FakeKernelFactory', ['kernel'])
  _popen = collections.namedtuple('FakePOpen', ['pid'])

  def list_kernel_ids(self):
    return FakeUsage.kernel_ids

  def get_kernel(self, kernel_id):
    if kernel_id == FakeUsage.kernel_ids[0]:
      pid = FakeUsage.pids[0]
    elif kernel_id == FakeUsage.kernel_ids[1]:
      pid = FakeUsage.pids[1]
    else:
      raise KeyError(kernel_id)
    return FakeKernelManager._kernel_factory(FakeKernelManager._popen(pid))


class ColabResourcesHandlerTest(testing.AsyncHTTPTestCase):
  """Tests for ChunkedFileDownloadHandler."""

  def get_app(self):
    """Setup code required by testing.AsyncHTTP[S]TestCase."""
    settings = {
        'base_url': '/',
        # The underyling ipaddress library sometimes doesn't think that
        # 127.0.0.1 is a proper loopback device.
        'local_hostnames': ['127.0.0.1'],
        'kernel_manager': FakeKernelManager(),
    }
    app = web.Application([], **settings)
    nb_server_app = FakeNotebookServer(app)
    _serverextension.load_jupyter_server_extension(nb_server_app)
    return app

  @mock.patch.object(
      subprocess,
      'check_output',
      # Use canned ps output.
      side_effect=FakeUsage.fake_check_output,
  )
  def testColabResources(self, mock_check_output):
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
      # Use canned ps and nvidia-smi output.
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

  @mock.patch.object(
      psutil,
      'disk_usage',
      # Return fake usage data.
      return_value=FakeUsage.disk_usage)
  @mock.patch.object(
      subprocess,
      'check_output',
      # Use canned ps output.
      side_effect=FakeUsage.fake_check_output,
  )
  def testColabResourcesFakeDisk(self, mock_check_output, mock_disk_usage):
    response = self.fetch('/api/colab/resources')
    self.assertEqual(response.code, 200)
    # Body is a JSON response.
    json_response = escape.json_decode(
        response.body[len(_handlers._XSSI_PREFIX):])  # pylint: disable=protected-access
    self.assertEqual(json_response['disk']['usage'], FakeUsage.disk_usage.used)
    self.assertEqual(json_response['disk']['limit'], FakeUsage.disk_usage.total)
