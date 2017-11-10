"""Colab-specific file helpers."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import base64
import collections
import os
import SimpleHTTPServer
import socket
import SocketServer
import threading
import uuid

import IPython
import portpicker
from google.colab import _js


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
      </span>""".format(input_id=input_id, output_id=output_id)))

  IPython.display.display(IPython.core.display.Javascript(_UPLOAD_JS))

  # First result is always an indication that the file picker has completed.
  result = _js.eval_script(
      'google.colab.files.uploadFiles("{input_id}", "{output_id}")'.format(
          input_id=input_id, output_id=output_id))
  files = collections.defaultdict(str)

  while result['action'] != 'complete':
    result = _js.eval_script(
        'google.colab.files.uploadFilesContinue("{output_id}")'.format(
            output_id=output_id))
    if result['action'] != 'append':
      # JS side uses a generator of promises to process all of the files- some
      # steps may not produce data for the Python side, so just proceed onto the
      # next message.
      continue
    files[result['file']] += base64.b64decode(result['data'])

  return dict(files)


class _V6Server(SocketServer.TCPServer):
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
  """

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

  _js.eval_script(
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


# TODO(b/68813764): Move to a separate JS file.
_UPLOAD_JS = """
(function(scope) {
function span(text, styleAttributes = {}) {
  const element = document.createElement('span');
  element.textContent = text;
  for (const key of Object.keys(styleAttributes)) {
    element.style[key] = styleAttributes[key];
  }
  return element;
}

// Max number of bytes which will be uploaded at a time.
const MAX_PAYLOAD_SIZE = 100 * 1024;
// Max amount of time to block waiting for the user.
const FILE_CHANGE_TIMEOUT_MS = 30 * 1000;

function uploadFiles(inputId, outputId) {
  const steps = uploadFilesStep(inputId, outputId);
  const outputElement = document.getElementById(outputId);
  // Cache steps on the outputElement to make it available for the next call
  // to uploadFilesContinue from Python.
  outputElement.steps = steps;

  return uploadFilesContinue(outputId);
}

// This is roughly an async generator (not supported in the browser yet),
// where there are multiple asynchronous steps and the Python side is going
// to poll for completion of each step.
// This uses a Promise to block the python side on completion of each step,
// then passes the result of the previous step as the input to the next step.
function uploadFilesContinue(outputId) {
  const outputElement = document.getElementById(outputId);
  const steps = outputElement.steps;

  const next = steps.next(outputElement.lastPromiseValue);
  return Promise.resolve(next.value.promise).then((value) => {
    // Cache the last promise value to make it available to the next
    // step of the generator.
    outputElement.lastPromiseValue = value;
    return next.value.response;
  });
}

/**
 * Generator function which is called between each async step of the upload
 * process.
 * @param {string} inputId Element ID of the input file picker element.
 * @param {string} outputId Element ID of the output display.
 * @return {!Iterable<!Object>} Iterable of next steps.
 */
function* uploadFilesStep(inputId, outputId) {
  const inputElement = document.getElementById(inputId);
  inputElement.disabled = false;

  const outputElement = document.getElementById(outputId);
  outputElement.innerHTML = '';

  const pickedPromise = new Promise((resolve) => {
    inputElement.addEventListener('change', (e) => {
      resolve(e.target.files);
    });
  });

  const cancel = document.createElement('button');
  inputElement.parentElement.appendChild(cancel);
  cancel.textContent = 'Cancel upload';
  const cancelPromise = new Promise((resolve) => {
    cancel.onclick = () => {
      resolve(null);
    };
  });

  // Cancel upload if user hasn't picked anything in timeout.
  const timeoutPromise = new Promise((resolve) => {
    setTimeout(() => {
      resolve(null);
    }, FILE_CHANGE_TIMEOUT_MS);
  });

  // Wait for the user to pick the files.
  const files = yield {
    promise: Promise.race([pickedPromise, timeoutPromise, cancelPromise]),
    response: {
      action: 'starting',
    }
  };

  if (!files) {
    return {
      response: {
        action: 'complete',
      }
    };
  }

  cancel.remove();

  // Disable the input element since further picks are not allowed.
  inputElement.disabled = true;

  for (const file of files) {
    const li = document.createElement('li');
    li.append(span(file.name, {fontWeight: 'bold'}));
    li.append(span(
        `(${file.type || 'n/a'}) - ${file.size} bytes, ` +
        `last modified: ${
                          file.lastModifiedDate ?
                              file.lastModifiedDate.toLocaleDateString() :
                              'n/a'
                        } - %`));
    const percent = span('0 done');
    li.appendChild(percent);

    outputElement.appendChild(li);

    const fileDataPromise = new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        resolve(e.target.result);
      };
      reader.readAsArrayBuffer(file);
    });
    // Wait for the data to be ready.
    let fileData = yield {
      promise: fileDataPromise,
      response: {
        action: 'continue',
      }
    };

    // Use a chunked sending to avoid message size limits. See b/62115660.
    let position = 0;
    while (position < fileData.byteLength) {
      const length = Math.min(fileData.byteLength - position, MAX_PAYLOAD_SIZE);
      const chunk = new Uint8Array(fileData, position, length);
      position += length;

      const base64 = btoa(String.fromCharCode.apply(null, chunk));
      yield {
        response: {
          action: 'append',
          file: file.name,
          data: base64,
        },
      };
      percent.textContent =
          `${Math.round((position / fileData.byteLength) * 100)} done`;
    }
  }

  // All done.
  yield {
    response: {
      action: 'complete',
    }
  };
}

scope.google = scope.google || {};
scope.google.colab = scope.google.colab || {};
scope.google.colab.files = {
  uploadFiles,
  uploadFilesContinue,
};
})(self);
"""
