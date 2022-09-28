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

import base64 as _base64
import collections as _collections
from http import server as _http_server
import json as _json
import os as _os
import pkgutil as _pkgutil
import socket as _socket
import socketserver as _socketserver
import urllib as _urllib
import uuid as _uuid

from google.colab import output as _output
import IPython as _IPython

__all__ = ['upload_file', 'upload', 'download', 'view']


def upload_file(filename):
  """Upload local (to the browser) file to the kernel.

  Blocks until the files are available.

  Args:
    filename: Name of the file to be written to

  Raises:
    ValueError: If multiple files were uploaded or no file is not uploaded.
  """

  uploaded_files = _upload_files(multiple=False)
  if not uploaded_files:
    raise ValueError('File has not been uploaded')
  if len(uploaded_files) > 1:
    raise ValueError('Multiple files received, please upload a single file')

  with open(filename, 'wb') as f:
    f.write(list(uploaded_files.values())[0])
  print('Saved {} to {}'.format(
      list(uploaded_files.keys())[0],
      _os.getcwd() + '/' + filename))


def upload():
  """Render a widget to upload local (to the browser) files to the kernel.

  Blocks until the files are available.

  Returns:
    A map of the form {<filename>: <file contents>} for all uploaded files.
  """

  uploaded_files = _upload_files(multiple=True)
  # Mapping from original filename to filename as saved locally.
  local_filenames = dict()
  for filename, data in uploaded_files.items():
    local_filename = local_filenames.get(filename)
    if not local_filename:
      local_filename = _get_unique_filename(filename)
      local_filenames[filename] = local_filename
      print('Saving {filename} to {local_filename}'.format(
          filename=filename, local_filename=local_filename))
    with open(local_filename, 'ab') as f:
      f.write(data)
  return uploaded_files


def _upload_file(filepath):
  """Render a widget to upload a local (to the browser) file to the kernel.

  Blocks until the file is available.

  Args:
    filepath: (optional, str) If set, the uploaded file will be saved to this
      path instead of using the name of the uploaded file.

  Returns:
    A 2-element tuple of (filename, contents), or None if uploading was
    cancelled.

  Raises:
    ValueError: If multiple files were uploaded.
  """
  uploaded_file = _upload_files(multiple=False)
  if not uploaded_file:
    return
  if len(uploaded_file) > 1:
    # Shouldn't happen but check anyways
    raise ValueError('Multiple files received, please upload a single file')
  filename, data = list(uploaded_file.items())[0]
  filename = filepath or _get_unique_filename(filename)
  with open(filename, 'wb') as f:
    f.write(data)
  return filename, data


def _upload_files(multiple):
  """Render a widget to upload local (to the browser) files to the kernel.

  Files are not written to storage.

  Blocks until the files are available.

  Args:
    multiple: (bool) Whether to show a multiple or single file upload dialog.

  Returns:
    A map of the form {<filename>: <file contents>} for all uploaded files.
  """
  upload_id = str(_uuid.uuid4())
  input_id = 'files-' + upload_id
  output_id = 'result-' + upload_id
  files_js = _pkgutil.get_data(__name__, 'resources/files.js').decode('utf8')

  _IPython.display.display(
      _IPython.core.display.HTML("""
     <input type="file" id="{input_id}" name="files[]" {multiple_text} disabled
        style="border:none" />
     <output id="{output_id}">
      Upload widget is only available when the cell has been executed in the
      current browser session. Please rerun this cell to enable.
      </output>
      <script>{files_js}</script> """.format(
          input_id=input_id,
          output_id=output_id,
          multiple_text='multiple' if multiple else '',
          files_js=files_js)))

  # First result is always an indication that the file picker has completed.
  result = _output.eval_js(
      'google.colab._files._uploadFiles("{input_id}", "{output_id}")'.format(
          input_id=input_id, output_id=output_id))
  files = _collections.defaultdict(bytes)

  while result['action'] != 'complete':
    result = _output.eval_js(
        'google.colab._files._uploadFilesContinue("{output_id}")'.format(
            output_id=output_id))
    if result['action'] != 'append':
      # JS side uses a generator of promises to process all of the files- some
      # steps may not produce data for the Python side, so just proceed onto the
      # next message.
      continue
    files[result['file']] += _base64.b64decode(result['data'])

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


class _FileHandler(_http_server.SimpleHTTPRequestHandler):
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
    _http_server.SimpleHTTPRequestHandler.end_headers(self)


def download(filename):
  """Downloads the file to the user's local disk via a browser download action.

  Args:
    filename: Name of the file on disk to be downloaded.

  Raises:
    OSError: if the file cannot be found.
  """

  if not _os.path.exists(filename):
    msg = 'Cannot find file: {}'.format(filename)
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
