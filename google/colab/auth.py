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
"""Colab-specific authentication helpers."""

# TODO(b/113878301): Test that imported modules do not appear in autocomplete.
from __future__ import absolute_import as _
from __future__ import division as _
from __future__ import print_function as _

import contextlib as _contextlib
import enum as _enum
import json as _json
import logging as _logging
import os as _os
import sqlite3 as _sqlite3  # pylint: disable=g-bad-import-order
import subprocess as _subprocess
import sys as _sys
import tempfile as _tempfile
import time as _time

from google.colab import _message
from google.colab import errors as _errors
from google.colab import files as _files
from google.colab import output as _output

__all__ = ['authenticate_service_account', 'authenticate_user']

_LOGGER = _logging.getLogger(__name__)


def _is_service_account_key(key_json_text):
  """Return true if the provided text is a JSON service credentials file."""
  try:
    key_obj = _json.loads(key_json_text)
  except _json.JSONDecodeError:
    return False
  if not key_obj or key_obj.get('type', '') != 'service_account':
    return False
  return True


class _CredentialType(_enum.Enum):
  """Enum class for selecting the type of credential that is expected."""
  NO_CHECK = 0
  USER = 1
  SERVICE_ACCOUNT = 2


def _check_adc(credential_type=_CredentialType.NO_CHECK):
  """Return whether the application default credential exists and is valid and, optionally, is the specified type of credential.

  Args:
    credential_type: (optional, _CredentialType) If specified, will also check
      that any present and valid credentials are of the specified type.

  Returns:
    bool. Whether there are credentials of the expected type present.
  """
  # Avoid forcing a kernel restart on users updating google.auth if they haven't
  # yet used google.auth.
  import google.auth as _google_auth  # pylint: disable=g-import-not-at-top
  import google.auth.transport.requests as _auth_requests  # pylint: disable=g-import-not-at-top
  # google-auth wants to warn the user if no project is set, which makes sense
  # for cloud-only users, but not in our case. We temporarily change the logging
  # level here to silence.
  logger = _logging.getLogger()
  log_level = logger.level
  logger.setLevel(_logging.ERROR)
  try:
    # refresh() will fail for service account credentials if some scope is not
    # provided
    creds, _ = _google_auth.default(scopes=['email'])
  except _google_auth.exceptions.DefaultCredentialsError:
    return False
  finally:
    logger.setLevel(log_level)
  transport = _auth_requests.Request()
  # Import here since it transitively brings in google.auth.
  from google.oauth2.service_account import Credentials as _ServiceAccountCredentials  # pylint: disable=g-import-not-at-top
  if credential_type == _CredentialType.SERVICE_ACCOUNT:
    # TODO(b/224641665) We should call refresh() on service account credentials
    # as well.
    return isinstance(creds, _ServiceAccountCredentials)
  try:
    creds.refresh(transport)
  except Exception as e:  # pylint:disable=broad-except
    _LOGGER.info('Failure refreshing credentials: %s', e)
  valid = creds.valid
  if valid and credential_type == _CredentialType.USER:
    return not isinstance(creds, _ServiceAccountCredentials)
  return valid


def _gcloud_login():
  """Call `gcloud auth login` with custom input handling."""
  # We want to run gcloud and provide user input on stdin; in order to do this,
  # we explicitly buffer the gcloud output and print it ourselves.
  gcloud_command = [
      'gcloud',
      'auth',
      'login',
      '--enable-gdrive-access',
      '--no-launch-browser',
      '--quiet',
  ]
  f, name = _tempfile.mkstemp()
  gcloud_process = _subprocess.Popen(
      gcloud_command,
      stdin=_subprocess.PIPE,
      stdout=f,
      stderr=_subprocess.STDOUT,
      universal_newlines=True)
  try:
    while True:
      _time.sleep(0.2)
      _os.fsync(f)
      prompt = open(name).read()
      if 'https' in prompt:
        break

    # TODO(b/147296819): Delete this line.
    get_code = input if _sys.version_info[0] == 3 else raw_input  # pylint: disable=undefined-variable
    # Combine the URL with the verification prompt to work around
    # https://github.com/jupyter/notebook/issues/3159
    prompt = prompt.rstrip()
    # Suppress the --launch-browser deprecation warning.
    # TODO(b/218377323): Remove this.
    prompt = '\n'.join(
        [line for line in prompt.splitlines() if 'launch-browser' not in line])
    code = get_code(prompt + ' ')
    gcloud_process.communicate(code.strip())
  finally:
    _os.close(f)
    _os.remove(name)
  if gcloud_process.returncode:
    raise _errors.AuthorizationError('Error fetching credentials')


def _get_adc_path():
  return _os.path.join(_os.environ.get('DATALAB_ROOT', '/'), 'content/adc.json')


def _install_adc():
  """Install the gcloud token as the Application Default Credential."""
  gcloud_db_path = _os.path.join(
      _os.environ.get('DATALAB_ROOT', '/'), 'content/.config/credentials.db')
  db = _sqlite3.connect(gcloud_db_path)
  c = db.cursor()
  ls = list(c.execute('SELECT * FROM credentials;'))
  adc_path = _get_adc_path()
  with open(adc_path, 'w') as f:
    f.write(ls[0][1])


# TODO(b/218377323): Remove.
def _enable_metadata_server_for_gcloud():
  with _output.temporary():
    _subprocess.run(
        'gcloud config unset compute/gce_metadata_read_timeout_sec',
        shell=True,
        check=True)
    gce_cache_path = _os.path.join(
        _os.environ.get('CLOUDSDK_CONFIG', ''), 'gce')
    if _os.path.exists(gce_cache_path):
      _os.remove(gce_cache_path)


@_contextlib.contextmanager
def _noop():
  """Null context manager, like contextlib.nullcontext in python 3.7+."""
  yield


def _setup_tpu_auth():
  """Pass current ADC to Tensorflow to setup auth."""
  # If we've got a TPU attached, we want to run a TF operation to provide
  # our new credentials to the TPU for GCS operations.
  import tensorflow as tf  # pylint: disable=g-import-not-at-top
  if tf.__version__.startswith('1'):
    colab_tpu_addr = _os.environ.get('COLAB_TPU_ADDR', '')
    with tf.compat.v1.Session('grpc://{}'.format(colab_tpu_addr)) as sess:
      with open(_get_adc_path()) as auth_info:
        tf.contrib.cloud.configure_gcs(sess, credentials=_json.load(auth_info))
  else:
    # pytype: skip-file
    tf.config.experimental_connect_to_cluster(
        tf.distribute.cluster_resolver.TPUClusterResolver())
    import tensorflow_gcs_config as _tgc  # pylint: disable=g-import-not-at-top
    _tgc.configure_gcs_from_colab_auth()


# pylint:disable=line-too-long
def authenticate_user(clear_output=True):
  """Ensures that the given user is authenticated.

  This will override any pre-existing service account credentials.

  Currently, this ensures that the Application Default Credentials
  (https://developers.google.com/identity/protocols/application-default-credentials)
  are available and valid.

  Args:
    clear_output: (optional, default: True) If True, clear any output related to
      the authorization process if it completes successfully. Any errors will
      remain (for debugging purposes).

  Returns:
    None.

  Raises:
    errors.AuthorizationError: If authorization fails.
  """
  use_auth_ephem = _os.environ.get('USE_AUTH_EPHEM', '0') == '1'
  colab_tpu_addr = _os.environ.get('COLAB_TPU_ADDR', '')
  configure_tpu_auth = ('COLAB_SKIP_AUTOMATIC_TPU_AUTH' not in _os.environ and
                        colab_tpu_addr and not use_auth_ephem)
  if _os.path.exists('/var/colab/mp'):
    raise NotImplementedError(__name__ + ' is unsupported in this environment.')
  if _check_adc(_CredentialType.USER):
    return
  if not use_auth_ephem:
    _os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = _get_adc_path()
  if not _check_adc(_CredentialType.USER):
    if use_auth_ephem:
      _message.blocking_request(
          'request_auth',
          request={'authType': 'auth_user_ephemeral'},
          timeout_sec=None)
      _enable_metadata_server_for_gcloud()
    else:
      context_manager = _output.temporary if clear_output else _noop
      with context_manager():
        _gcloud_login()
      _install_adc()
      if configure_tpu_auth:
        _setup_tpu_auth()
  if _check_adc(_CredentialType.USER):
    return
  raise _errors.AuthorizationError('Failed to fetch user credentials')


def authenticate_service_account():
  """Ensures that a service account key is present and valid.

  This will override any pre-existing user credentials.

  If no key is present, the user is prompted to upload one.

  Returns:
    None.

  Raises:
    errors.AuthorizationError: If authorization fails.
  """
  if _os.path.exists('/var/colab/mp'):
    raise NotImplementedError(__name__ + ' is unsupported in this environment.')
  if _check_adc(_CredentialType.SERVICE_ACCOUNT):
    return
  colab_tpu_addr = _os.environ.get('COLAB_TPU_ADDR', '')
  configure_tpu_auth = ('COLAB_SKIP_AUTOMATIC_TPU_AUTH' not in _os.environ and
                        colab_tpu_addr)
  _os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = _get_adc_path()
  if not _check_adc(_CredentialType.SERVICE_ACCOUNT):
    with _output.temporary():
      print(
          'Upload the private key for your service account.\n\nSee the guide at https://cloud.google.com/iam/docs/creating-managing-service-account-keys#iam-service-account-keys-create-console for help.\n\n'
      )
      # TODO(b/226659795): Offer programmatic option, https://cloud.google.com/iam/docs/creating-managing-service-account-keys#iam-service-account-keys-create-gcloud
      for _ in range(3):
        uploaded_file = _files._upload_file(_get_adc_path())  # pylint: disable=protected-access
        if not uploaded_file:
          # Upload was cancelled.
          return
        _, content = uploaded_file
        if _is_service_account_key(content):
          if configure_tpu_auth:
            _setup_tpu_auth()
          break
        print('Invalid credentials: please try again.\n\n')
      else:
        raise _errors.AuthorizationError('Failed to fetch user credentials')
  if _check_adc(_CredentialType.SERVICE_ACCOUNT):
    import google.auth as _google_auth  # pylint: disable=g-import-not-at-top
    creds, _ = _google_auth.default()
    print('Successfully saved credentials for', creds.service_account_email)
    return
  raise _errors.AuthorizationError('Failed to fetch user credentials')
