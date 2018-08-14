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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import contextlib
import getpass
import logging
import os
import sqlite3  # pylint: disable=g-bad-import-order
import subprocess
import tempfile
import time

import google.auth
import google.auth.transport.requests
from google.colab import errors
from google.colab import output


def _check_adc():
  """Return whether the application default credential exists and is valid."""
  try:
    creds, _ = google.auth.default()
  except google.auth.exceptions.DefaultCredentialsError:
    return False
  transport = google.auth.transport.requests.Request()
  try:
    creds.refresh(transport)
  except Exception as e:  # pylint:disable=broad-except
    logging.info('Failure refreshing credentials: %s', e)
  return creds.valid


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
  f, name = tempfile.mkstemp()
  gcloud_process = subprocess.Popen(
      gcloud_command,
      stdin=subprocess.PIPE,
      stdout=f,
      stderr=subprocess.STDOUT,
      universal_newlines=True)
  try:
    while True:
      time.sleep(0.2)
      os.fsync(f)
      prompt = open(name).read()
      if 'https' in prompt:
        break

    # Combine the URL with the verification prompt to work around
    # https://github.com/jupyter/notebook/issues/3159
    prompt = prompt.rstrip()
    code = getpass.getpass(prompt + '\n\nEnter verification code: ')
    gcloud_process.communicate(code.strip())
  finally:
    os.close(f)
    os.remove(name)
  if gcloud_process.returncode:
    raise errors.AuthorizationError('Error fetching credentials')


def _get_adc_path():
  return os.path.join(os.environ.get('DATALAB_ROOT', '/'), 'content/adc.json')


def _install_adc():
  """Install the gcloud token as the Application Default Credential."""
  gcloud_db_path = os.path.join(
      os.environ.get('DATALAB_ROOT', '/'), 'content/.config/credentials.db')
  db = sqlite3.connect(gcloud_db_path)
  c = db.cursor()
  ls = list(c.execute('SELECT * FROM credentials;'))
  adc_path = _get_adc_path()
  with open(adc_path, 'w') as f:
    f.write(ls[0][1])


@contextlib.contextmanager
def _noop():
  """Null context manager, like contextlib.nullcontext in python 3.7+."""
  yield


# pylint:disable=line-too-long
def authenticate_user(clear_output=True):
  """Ensures that the given user is authenticated.

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
  if _check_adc():
    return
  os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = _get_adc_path()
  if not _check_adc():
    context_manager = output.temporary if clear_output else _noop
    with context_manager():
      _gcloud_login()
    _install_adc()
  if _check_adc():
    return
  raise errors.AuthorizationError('Failed to fetch user credentials')
