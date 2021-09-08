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
"""Private utility functions."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import json
import sys
# pytype: disable=import-error
from IPython import display

_id_counter = 0


def flush_all():
  """Flushes stdout/stderr/matplotlib."""
  sys.stdout.flush()
  sys.stderr.flush()
  # pylint: disable=g-import-not-at-top
  try:
    from ipykernel.pylab.backend_inline import flush_figures
  except ImportError:
    # older ipython
    from IPython.kernel.zmq.pylab.backend_inline import flush_figures

  flush_figures()


def get_locally_unique_id(prefix='id'):
  """"Returns id which is unique with the session."""
  global _id_counter
  _id_counter += 1
  return prefix + str(_id_counter)


def serve_kernel_port_as_iframe(port,
                                path='/',
                                width='100%',
                                height='400',
                                cache_in_notebook=False):
  """Displays an iframe in the output to a port on the kernel.

  This allows viewing URLs hosted on the kernel from output frames.

  Args:
    port: The kernel port to be exposed to the client.
    path: The path to be navigated to.
    width: The iframe width in CSS size.
    height: The iframe height in CSS size (pixels).
    cache_in_notebook: True if the displayed content should be cached in the
      notebook for offline viewing.
  """
  code = """(async (port, path, width, height, cache, element) => {
    if (!google.colab.kernel.accessAllowed && !cache) {
      return;
    }
    element.appendChild(document.createTextNode(''));
    const url = await google.colab.kernel.proxyPort(port, {cache});
    const iframe = document.createElement('iframe');
    iframe.src = new URL(path, url).toString();
    iframe.height = height;
    iframe.width = width;
    iframe.style.border = 0;
    element.appendChild(iframe);
  })""" + '({port}, {path}, {width}, {height}, {cache}, window.element)'.format(
      port=port,
      path=json.dumps(path),
      width=json.dumps(width),
      height=json.dumps(height),
      cache=json.dumps(cache_in_notebook))
  display.display(display.Javascript(code))


def serve_kernel_port_as_window(port, path='/', anchor_text=None):
  """Displays a link in the output to open a browser tab to a port on the kernel.

  This allows viewing URLs hosted on the kernel in new browser tabs.

  The URL will only be valid for the current user while the notebook is open in
  Colab.

  Args:
    port: The kernel port to be exposed to the client.
    path: The path to be navigated to.
    anchor_text: Text content of the anchor link.
  """
  if not anchor_text:
    anchor_text = 'https://localhost:{port}{path}'.format(port=port, path=path)

  code = """(async (port, path, text, element) => {
    if (!google.colab.kernel.accessAllowed) {
      return;
    }
    element.appendChild(document.createTextNode(''));
    const url = await google.colab.kernel.proxyPort(port);
    const anchor = document.createElement('a');
    anchor.href = new URL(path, url).toString();
    anchor.target = '_blank';
    anchor.setAttribute('data-href', url + path);
    anchor.textContent = text;
    element.appendChild(anchor);
  })""" + '({port}, {path}, {text}, window.element)'.format(
      port=port, path=json.dumps(path), text=json.dumps(anchor_text))
  display.display(display.Javascript(code))
