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
import json

from google.colab import _ipython
from google.colab import _message

_json_decoder = json.JSONDecoder()


def eval_js(script, ignore_result=False, timeout_sec=None):
  """Evaluates the Javascript within the context of the current cell.

  Args:
    script: The javascript string to be evaluated
    ignore_result: If true, will return immediately
     and result from javascript side will be ignored.
    timeout_sec: blocks for that many seconds.

  Returns:
    Result of the Javascript evaluation or None if ignore_result.
  """
  args = ['cell_javascript_eval', {'script': script}]
  kernel = _ipython.get_kernel()
  request_id = _message.send_request(*args, parent=kernel.shell.parent_header)
  if ignore_result:
    return
  return _message.read_reply_from_input(request_id, timeout_sec)


_functions = {}


def register_callback(function_name, callback):
  """Registers a function as a target invokable by Javacript in outputs.

  This exposes the Python function as a target which may be invoked by
  Javascript executing in Colab output frames.

  This callback can be called from javascript side using:
  colab.kernel.invokeFunction(function_name, [1, 2, 3], {'hi':'bye'})
  then it will invoke callback(1, 2, 3, hi="bye")

  Args:
    function_name: string
    callback: function that possibly takes positional and keyword arguments
    that will be passed via invokeFunction()
  """
  _functions[function_name] = callback


def _invoke_function(function_name, json_args, json_kwargs):
  """Invokes callback with given function_name.

  This function is meant to be used by frontend when proxying
  data from secure iframe into kernel.  For example:

  _invoke_function(fn_name, "'''"   + JSON.stringify(data) + "'''")

  Note the triple quotes: valid JSON cannot contain triple quotes,
  so this is a valid literal.

  Args:
    function_name: string
    json_args: string containing valid json, provided by user.
    json_kwargs: string containing valid json, provided by user.

  Returns:
    The value returned by the callback.

  Raises:
    ValueError: if the registered function cannot be found.
  """
  args = _json_decoder.decode(json_args)
  kwargs = _json_decoder.decode(json_kwargs)

  callback = _functions.get(function_name, None)
  if not callback:
    raise ValueError('Function not found: {function_name}'.format(
        function_name=function_name))

  return callback(*args, **kwargs)
