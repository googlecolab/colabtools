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
"""Colab-specific file helpers."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import base64
import collections
import os
import socket
import threading
import uuid

import IPython
import portpicker
import six
from six.moves import SimpleHTTPServer
from six.moves import socketserver

from google.colab import output


def upload():
  """Renders widget to upload local (to the browser) files to the kernel.

  Blocks until the files are available.

  Returns:
    A map of the form {<filename>: <file contents>} for all uploaded files.
  """
  upload_id = str(uuid.uuid4())
  input_id = 'files-' + upload_id
  output_id = 'result-' + upload_id

  IPython.display.display(
      IPython.core.display.HTML("""
     <input type="file" id="{input_id}" name="files[]" multiple disabled />
     <output id="{output_id}">
      Upload widget is only available when the cell has been executed in the
      current browser session. Please rerun this cell to enable.
      </output>
      <script src="/nbextensions/google.colab/files.js"></script> """.format(
          input_id=input_id, output_id=output_id)))

  # First result is always an indication that the file picker has completed.
  result = output.eval_js(
      'google.colab._files._uploadFiles("{input_id}", "{output_id}")'.format(
          input_id=input_id, output_id=output_id))
  files = collections.defaultdict(six.binary_type)
  # Mapping from original filename to filename as saved locally.
  local_filenames = dict()

  while result['action'] != 'complete':
    result = output.eval_js(
        'google.colab._files._uploadFilesContinue("{output_id}")'.format(
            output_id=output_id))
    if result['action'] != 'append':
      # JS side uses a generator of promises to process all of the files- some
      # steps may not produce data for the Python side, so just proceed onto the
      # next message.
      continue
    data = base64.b64decode(result['data'])
    filename = result['file']

    files[filename] += data
    local_filename = local_filenames.get(filename)
    if not local_filename:
      local_filename = _get_unique_filename(filename)
      local_filenames[filename] = local_filename
      print('Saving {filename} to {local_filename}'.format(
          filename=filename, local_filename=local_filename))
    with open(local_filename, 'ab') as f:
      f.write(data)

  return dict(files)


def _get_unique_filename(filename):
  if not os.path.lexists(filename):
    return filename
  counter = 1
  while True:
    path, ext = os.path.splitext(filename)
    new_filename = '{} ({}){}'.format(path, counter, ext)
    if not os.path.lexists(new_filename):
      return new_filename
    counter += 1


class _V6Server(socketserver.TCPServer):
  address_family = socket.AF_INET6


class _FileHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
  """SimpleHTTPRequestHandler with a couple tweaks."""

  def translate_path(self, path):
    # Client specifies absolute paths.
    return path

  def log_message(self, fmt, *args):
    # Suppress logging since it's on the background. Any errors will be reported
    # via the handler.
    pass

  def end_headers(self):
    # Do not cache the response in the notebook, since it may be quite large.
    self.send_header('x-colab-notebook-cache-control', 'no-cache')
    SimpleHTTPServer.SimpleHTTPRequestHandler.end_headers(self)


def download(filename):
  """Downloads the file to the user's local disk via a browser download action.

  Args:
    filename: Name of the file on disk to be downloaded.

  Raises:
    OSError: if the file cannot be found.
  """

  if not os.path.exists(filename):
    msg = 'Cannot find file: {}'.format(filename)
    if six.PY2:
      raise OSError(msg)
    else:
      raise FileNotFoundError(msg)  # pylint: disable=undefined-variable

  started = threading.Event()
  port = portpicker.pick_unused_port()

  def server_entry():
    httpd = _V6Server(('::', port), _FileHandler)
    started.set()
    # Handle a single request then exit the thread.
    httpd.handle_request()

  thread = threading.Thread(target=server_entry)
  thread.start()
  started.wait()

  output.eval_js(
      """
      (async function() {
        const response = await fetch('https://localhost:%(port)d%(path)s');
        if (!response.ok) {
          throw new Error('Failed to download: ' + response.statusText);
        }
        const blob = await response.blob();

        const a = document.createElement('a');
        a.href = window.URL.createObjectURL(blob);
        a.download = '%(name)s';
        a.click();
      })();
  """ % {
      'port': port,
      'path': os.path.abspath(filename),
      'name': os.path.basename(filename),
  })
