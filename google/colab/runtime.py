"""Functionality for working with the Colab runtime."""

import http as _http
import os as _os
from google.colab import errors as _errors
from google.colab import output as _output
import httplib2 as _httplib2

__all__ = ['unassign']

_IS_EXTERNAL_COLAB = True


def unassign():
  """Instruct Colab to unassign the currently assigned runtime.

  This function allows a notebook cell to programmatically end the notebook's
  session by unassigning the runtime. This can help users save resources by
  disconnecting soon after execution is finished.

  Raises:
    google.colab.errors.RuntimeManagementError: Error communicating with the
        backend service.
  """
  if not _IS_EXTERNAL_COLAB:
    raise _errors.RuntimeManagementError(
        'This operation is only supported in external Colab.')
  h = _httplib2.Http()
  runtime_server_addr = _os.environ.get('TBE_RUNTIME_ADDR')
  if not runtime_server_addr:
    raise _errors.RuntimeManagementError(
        'Unable to find the runtime management service.')
  resp, _ = h.request(f'http://{runtime_server_addr}/unassign', 'POST')
  if resp.status != _http.HTTPStatus.OK:
    raise _errors.RuntimeManagementError('Unable to request VM unassignment.')
  _output.eval_js('google.colab.kernel.disconnect();', ignore_result=True)
