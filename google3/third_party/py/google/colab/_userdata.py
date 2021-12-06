"""API to access user secrets."""

from google.colab._message import blocking_request as BlockingRequest


def Get(*args):
  """Fetchets the value for specified secret keys.

  Args:
    *args: identifiers for the secret to fetch.

  Returns:
    Stored secret
  """
  return BlockingRequest('GetSecret', request={'keys': args}, timeout_sec=None)
