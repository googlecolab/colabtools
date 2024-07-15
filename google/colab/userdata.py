"""API to access user secrets."""

import re as _re
import threading

from google.colab import _message
from google.colab import errors


class NotebookAccessError(Exception):
  """Exception thrown when the current notebook doesn't have access to the requested secret."""

  def __init__(self, key):
    super().__init__(f'Notebook does not have access to secret {key}')


class SecretNotFoundError(errors.Error):
  """Exception thrown when the requested secret is not found."""

  def __init__(self, key):
    super().__init__(f'Secret {key} does not exist.')


class TimeoutException(errors.Error):
  """Exception thrown when requesting a secret times out."""

  def __init__(self, key):
    super().__init__(
        f'Requesting secret {key} timed out. Secrets can only be fetched when'
        ' running from the Colab UI.'
    )


_userdata_lock = threading.Lock()


def get(key):
  """Fetches the value for specified secret keys.

  This is safe to use from multiple threads.

  Args:
    key: Identifier of the secret to fetch.

  Returns:
    Stored secret

  Raises:
    TimeoutException: If the request times out, usually due to being run from an
    export where the Colab UI is not available.
    NotebookAccessError: If the notebook does not have access to the requested
    secret.
    SecretNotFoundError: If the requested secret is not found.
  """
  if not key or not isinstance(key, str):
    raise ValueError('Please enter a valid secret name')
  if _re.search(r'\s', key):
    raise ValueError('Secret name cannot contain spaces or whitespace')
  # blocking_request is not thread-safe, use a global lock to keep the function
  # thread-safe.
  with _userdata_lock:
    resp = _message.blocking_request(
        'GetSecret', request={'key': key}, timeout_sec=10
    )
  if not resp:
    raise TimeoutException(key)
  if not resp.get('exists', False):
    raise SecretNotFoundError(key)
  if not resp.get('access', False):
    raise NotebookAccessError(key)
  return resp.get('payload', '')
