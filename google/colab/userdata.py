"""API to access user secrets."""

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


def get(key):
  """Fetchets the value for specified secret keys.

  Args:
    key: Identifier of the secret to fetch.

  Returns:
    Stored secret

  Raises:
    NotebookAccessError: If the notebook does not have access to the requested
    secret.
    SecretNotFoundError: If the requested secret is not found.
  """
  resp = _message.blocking_request(
      'GetSecret', request={'key': key}, timeout_sec=None
  )
  if not resp.get('exists', False):
    raise SecretNotFoundError(key)
  if not resp.get('access', False):
    raise NotebookAccessError(key)
  return resp.get('payload', '')
