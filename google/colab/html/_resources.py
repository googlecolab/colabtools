"""Fetches resources."""

import pkgutil

_cache = {}


def get_data(module, relative_path):
  """Gets data using `pkgutil` module should be passed in as __name__."""
  key = module + relative_path
  if key in _cache:
    return _cache[key]
  data = pkgutil.get_data(module, relative_path)
  _cache[key] = data
  return data
