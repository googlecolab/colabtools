"""API to access user secrets."""

from google.colab import _message


class NotebookAccessError(Exception):
  """Exception thrown then the current notebook doesn't have access to the requested secret."""

  def __init__(self, key):
    super().__init__(f'Notebook does not have access to secret {key}')


def get(key):
  """Fetchets the value for specified secret keys.

  Args:
    key: Identifier of the secret to fetch.

  Returns:
    Stored secret

  Raises:
    NotebookAccessError: If the notebook does not have access to the requested
    secret.
  """
  resp = _message.blocking_request(
      'GetSecret', request={'key': key}, timeout_sec=None
  )
  access = resp.get('access', False)
  if not access:
    # TODO(b/294619193): Open the user secrets pane so that they can grant
    # access.
    raise NotebookAccessError(key)
  return resp.get('payload', '')
