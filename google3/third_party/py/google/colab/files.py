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

from __future__ import absolute_import as _
from __future__ import division as _
from __future__ import print_function as _

import base64 as _base64
import collections as _collections
import json as _json
import os as _os
import socket as _socket
import uuid as _uuid

import IPython as _IPython
import six as _six
from six.moves import SimpleHTTPServer as _SimpleHTTPServer
from six.moves import socketserver as _socketserver
from six.moves import urllib as _urllib

from google.colab import output as _output

__all__ = ['upload', 'download', 'view']


def upload():
  """Render a widget to upload local (to the browser) files to the kernel.

  Blocks until the files are available.

  Returns:
    A map of the form {<filename>: <file contents>} for all uploaded files.
  """
  upload_id = str(_uuid.uuid4())
  input_id = 'files-' + upload_id
  output_id = 'result-' + upload_id

  _IPython.display.display(
      _IPython.core.display.HTML("""
     <input type="file" id="{input_id}" name="files[]" multiple disabled
        style="border:none" />
     <output id="{output_id}">
      Upload widget is only available when the cell has been executed in the
      current browser session. Please rerun this cell to enable.
      </output>
      <script src="/nbextensions/google.colab/files.js"></script> """.format(
          input_id=input_id, output_id=output_id)))

  # First result is always an indication that the file picker has completed.
  result = _output.eval_js(
      'google.colab._files._uploadFiles("{input_id}", "{output_id}")'.format(
          input_id=input_id, output_id=output_id))
  files = _collections.defaultdict(_six.binary_type)
  # Mapping from original filename to filename as saved locally.
  local_filenames = dict()

  while result['action'] != 'complete':
    result = _output.eval_js(
        'google.colab._files._uploadFilesContinue("{output_id}")'.format(
            output_id=output_id))
    if result['action'] != 'append':
      # JS side uses a generator of promises to process all of the files- some
      # steps may not produce data for the Python side, so just proceed onto the
      # next message.
      continue
    data = _base64.b64decode(result['data'])
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
  if not _os.path.lexists(filename):
    return filename
  counter = 1
  while True:
    path, ext = _os.path.splitext(filename)
    new_filename = '{} ({}){}'.format(path, counter, ext)
    if not _os.path.lexists(new_filename):
      return new_filename
    counter += 1


class _V6Server(_socketserver.TCPServer):
  address_family = _socket.AF_INET6


class _FileHandler(_SimpleHTTPServer.SimpleHTTPRequestHandler):
  """SimpleHTTPRequestHandler with a couple tweaks."""

  def translate_path(self, path):
    # Client specifies absolute paths.
    return _urllib.parse.unquote(path)

  def log_message(self, fmt, *args):
    # Suppress logging since it's on the background. Any errors will be reported
    # via the handler.
    pass

  def end_headers(self):
    # Do not cache the response in the notebook, since it may be quite large.
    self.send_header('x-colab-notebook-cache-control', 'no-cache')
    _SimpleHTTPServer.SimpleHTTPRequestHandler.end_headers(self)


def download(filename):
  """Downloads the file to the user's local disk via a browser download action.

  Args:
    filename: Name of the file on disk to be downloaded.

  Raises:
    OSError: if the file cannot be found.
  """

  if not _os.path.exists(filename):
    msg = 'Cannot find file: {}'.format(filename)
    if _six.PY2:
      raise OSError(msg)
    else:
      raise FileNotFoundError(msg)  # pylint: disable=undefined-variable

  comm_manager = _IPython.get_ipython().kernel.comm_manager
  comm_id = 'download_' + str(_uuid.uuid4())

  def download_file(comm, _):
    f = open(filename, mode='rb')

    def on_message(_):
      chunk = f.read(1024 * 1024)
      if chunk:
        comm.send({}, None, [chunk])
      else:
        comm.close()
        f.close()
        comm_manager.unregister_target(comm_id, download_file)

    comm.on_msg(on_message)

  comm_manager.register_target(comm_id, download_file)

  _IPython.display.display(
      _IPython.display.Javascript("""
    async function download(id, filename, size) {
      if (!google.colab.kernel.accessAllowed) {
        return;
      }
      const div = document.createElement('div');
      const label = document.createElement('label');
      label.textContent = `Downloading "${filename}": `;
      div.appendChild(label);
      const progress = document.createElement('progress');
      progress.max = size;
      div.appendChild(progress);
      document.body.appendChild(div);

      const buffers = [];
      let downloaded = 0;

      const channel = await google.colab.kernel.comms.open(id);
      // Send a message to notify the kernel that we're ready.
      channel.send({})

      for await (const message of channel.messages) {
        // Send a message to notify the kernel that we're ready.
        channel.send({})
        if (message.buffers) {
          for (const buffer of message.buffers) {
            buffers.push(buffer);
            downloaded += buffer.byteLength;
            progress.value = downloaded;
          }
        }
      }
      const blob = new Blob(buffers, {type: 'application/binary'});
      const a = document.createElement('a');
      a.href = window.URL.createObjectURL(blob);
      a.download = filename;
      div.appendChild(a);
      a.click();
      div.remove();
    }
  """))
  size = _os.path.getsize(filename)
  name = _os.path.basename(filename)
  _IPython.display.display(
      _IPython.display.Javascript('download({id}, {name}, {size})'.format(
          id=_json.dumps(comm_id), name=_json.dumps(name), size=size)))


def view(filepath):
  """Views a file in Colab's file viewer.

  If the path is to a directory then the directory will be opened in the file
  browser.

  Args:
    filepath: Path to the file on disk to be viewed.

  Raises:
    FileNotFoundError: if the file cannot be found.
  """

  if not _os.path.exists(filepath):
    msg = 'Cannot find file: {}'.format(filepath)
    if _six.PY2:
      raise OSError(msg)  # pylint: disable=g-doc-exception
    else:
      raise FileNotFoundError(msg)

  filepath = _os.path.abspath(filepath)
  # Remove the filesystem prefix if it's present since the kernel manager
  # paths will be rooted at DATALAB_ROOT.
  if 'DATALAB_ROOT' in _os.environ:
    if filepath.startswith(_os.environ['DATALAB_ROOT']):
      filepath = filepath[len(_os.environ['DATALAB_ROOT']):]

  _IPython.display.display(
      _IPython.display.Javascript("""
      ((filepath) => {{
        if (!google.colab.kernel.accessAllowed) {{
          return;
        }}
        google.colab.files.view(filepath);
      }})(""" + _json.dumps(filepath) + ')'))
