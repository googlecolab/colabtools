"""Common error types used across Colab python functions."""


class Error(Exception):
  """Base class for all Colab errors."""


class AuthorizationError(Error):
  """Authorization-related failures."""
