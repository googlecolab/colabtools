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
