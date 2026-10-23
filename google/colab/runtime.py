"""Functionality for working with the Colab runtime."""

import base64 as _base64
import http as _http
import json as _json
import os as _os
import urllib as _urllib

import google.auth as _google_auth
import google.auth.transport.requests as _auth_requests
from google.colab import _message
from google.colab import auth as _auth
from google.colab import errors as _errors
from google.colab import output as _output
import httplib2 as _httplib2

__all__ = ['export_container', 'unassign']

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
        'This operation is only supported in external Colab.'
    )
  h = _httplib2.Http()
  runtime_server_addr = _os.environ.get('TBE_RUNTIME_ADDR')
  if not runtime_server_addr:
    raise _errors.RuntimeManagementError(
        'Unable to find the runtime management service.'
    )
  resp, _ = h.request(f'http://{runtime_server_addr}/unassign', 'POST')
  if resp.status != _http.HTTPStatus.OK:
    raise _errors.RuntimeManagementError('Unable to request VM unassignment.')
  _output.eval_js('google.colab.kernel.disconnect();', ignore_result=True)


def export_container(project_id, image_name=''):
  """Instruct Colab to export the notebook container to GCP's Artifact Registry.

  This function allows a notebook cell to programmatically export the users
  container - any downloaded data, installed packages, plus the users notebook -
  to Artifact Registry under
  us-docker.pkg.dev/<project_id>/colab-notebooks/<notebook-name>.
  Subsequent exports will createnew revisions of a notebook image.

  This function requires that the user has previously authorized via
  auth.authenticate_user. The URL of the newly uploaded image is returned on
  success.

  Args:
    project_id (string): A project ID is required. This function will create an
      artifact repository called "colab-notebooks" if it does not already exist
      in the target project.
    image_name (optional, string): If set, use the given image name. If unset,
      use the name of the notebook.

  Raises:
    google.colab.errors.AuthorizationError: Error fetching credentials
        (user needs to have run auth.authenticate_user prior to invoking this
        method).
    google.colab.errors.RuntimeManagementError: Error communicating with the
        backend service.

  Returns:
    string - a fully qualified path to the newly pushed repository
             (eg a docker image URL)
  """

  if not project_id:
    raise _errors.Error(
        'Invalid argument - project_id must be a GCP project ID.'
    )

  if not _IS_EXTERNAL_COLAB:
    raise _errors.RuntimeManagementError(
        'This operation is only supported in external Colab.'
    )

  if not _auth._check_adc(_auth._CredentialType.USER):  # pylint: disable=protected-access
    raise _errors.AuthorizationError(
        'No authorization - please run auth.authenticate_user() first.'
    )

  try:
    transport = _auth_requests.Request()
    creds, _ = _google_auth.default()
    creds.refresh(transport)
  except Exception as e:
    raise _errors.AuthorizationError('Failed to fetch access token - %s' % e)

  cred_info = creds.get_cred_info()

  server = 'us-docker.pkg.dev'

  registry_auth = {
      'username': 'oauth2accesstoken',
      'password': creds.token,
      'email': cred_info.get('principal'),
      'servername': server,
  }
  registry_auth_data = _base64.b64encode(
      _json.dumps(registry_auth).encode('utf-8')
  )

  h = _httplib2.Http()
  runtime_server_addr = _os.environ.get('TBE_RUNTIME_ADDR')
  if not runtime_server_addr:
    raise _errors.RuntimeManagementError(
        'Unable to find the runtime management service.'
    )

  nb_name = image_name
  if not nb_name:
    nb_name = _message.blocking_request('get_notebook_name')

  nb = _message.blocking_request('get_ipynb')
  with open('/content/notebook.ipynb', 'w') as f:
    f.write(_json.dumps(nb['ipynb'], indent=2))

  target_image_name = f'{server}/{project_id}/colab-notebooks/{nb_name}'

  post_data = {
      'image_name': target_image_name,
      'changes': [],
      'x-registry-auth': registry_auth_data,
  }
  body = _urllib.parse.urlencode(post_data)
  headers = {'Content-Type': 'application/x-www-form-urlencoded'}

  resp, _ = h.request(
      uri=f'http://{runtime_server_addr}/export',
      method='POST',
      body=body,
      headers=headers,
  )
  if resp.status != _http.HTTPStatus.OK:
    raise _errors.RuntimeManagementError('Unable to request container export.')

  return target_image_name
