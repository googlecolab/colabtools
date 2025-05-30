"""Routines for extracting information about pip installed packages.

The intent is to provide users a useful warning if they !pip install a package
that is already loaded in sys.modules.
"""

import collections
import importlib
import itertools
import re
import sys
import uuid
from IPython.core.display import _display_mimetype

__all__ = ["is_pip_install_command", "print_previous_import_warning"]

_COLAB_DATA_MIMETYPE = "application/vnd.colab-display-data+json"


def is_pip_install_command(cmd, *args, **kwargs):  # pylint: disable=unused-argument
  """Check if cmd represents a pip command."""
  # Check if the command starts with pip/pip2/pip3 and a space.
  # This won't trigger on every pip invocation, but will catch the most common.
  return re.match(r"^pip[23]?\s+install", cmd.strip())


def _extract_installed_packages(pip_output):
  """Extract the list of successfully installed packages from pip output."""
  regex = re.compile(
      r"^(?:\x1b\[0m)?\s*Successfully installed (.*)$", re.MULTILINE
  )
  results = regex.findall(pip_output)
  return itertools.chain(*map(str.split, results))


def _extract_toplevel_packages(pip_output):
  """Extract the list of toplevel packages associated with a pip install."""
  toplevel = collections.defaultdict(set)
  for m, ps in importlib.metadata.packages_distributions().items():
    for p in ps:
      toplevel[p].add(m)
  for pv in _extract_installed_packages(pip_output):
    package = pv[: pv.rfind("-")]
    for module in toplevel.get(package, set()):
      yield module


def _previously_imported_packages(pip_output):
  """List all previously imported packages from a pip install."""
  installed = set(_extract_toplevel_packages(pip_output))
  return sorted(installed.intersection(set(sys.modules)))


def print_previous_import_warning(output):
  """Prints a warning about previously imported packages."""
  packages = _previously_imported_packages(output)
  if packages:
    # display a list of packages using the colab-display-data mimetype, which
    # will be printed as a warning + restart button by the Colab frontend.
    _display_mimetype(
        _COLAB_DATA_MIMETYPE,
        (
            {
                "pip_warning": {
                    "packages": packages,
                },
                "id": uuid.uuid4().hex,
            },
        ),
        raw=True,
    )
