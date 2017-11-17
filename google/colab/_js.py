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
"""Colab helpers for interacting with JavaScript in outputframes."""

from ipykernel import kernelapp
from google.colab import _message


def eval_script(script, ignore_result=False):
  """Evaluates the Javascript within the context of the current cell.

  Args:
    script: The javascript string to be evaluated
    ignore_result: If true, do not block waiting for a response.

  Returns:
    Result of the Javascript evaluation or None if ignore_result.
  """
  args = ['cell_javascript_eval', {'script': script}]
  kwargs = {
      'parent': kernelapp.IPKernelApp.instance().kernel.shell.parent_header
  }
  request_id = _message.send_request(*args, **kwargs)
  if ignore_result:
    return
  return _message.read_reply_from_input(request_id)
