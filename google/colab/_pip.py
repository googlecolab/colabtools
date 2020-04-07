"""Routines for extracting information about pip installed packages.

The intent is to provide users a useful warning if they !pip install a package
that is already loaded in sys.modules.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import itertools
import os
import re
import site
import sys
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
  regex = re.compile("^Successfully installed (.*)$", re.MULTILINE)
  results = regex.findall(pip_output)
  return itertools.chain(*map(str.split, results))


def _get_distinfo_path(distname, paths):
  """Find the filesystem path to a package's distribution info.

  Distribution names must be treated as case-insensitive, with '-' and '_'
  characters treated as equivalent
  (See https://www.python.org/dev/peps/pep-0426/#name).

  Args:
    distname: distribution name.
    paths: list of directory path to search

  Returns:
    path: (string or None) the valid filesystem path to the distribution.
  """
  paths = [p for p in paths if os.path.exists(p)]
  if not paths:
    return None

  # Python packages can be installed as wheels or as eggs. Account for both
  # (see https://packaging.python.org/discussions/wheel-vs-egg/)
  distinfo = ["{}.dist-info".format(distname), "{}.egg-info".format(distname)]

  def normalize_dist(dist):
    return dist.lower().replace("_", "-")

  distinfo = [normalize_dist(info) for info in distinfo]

  for path in paths:
    path_map = {normalize_dist(f): f for f in os.listdir(path)}
    for info in distinfo:
      if info in path_map:
        joined = os.path.join(path, path_map[info])
        if os.path.isdir(joined):
          return joined

  return None


def _extract_toplevel_packages(pip_output):
  """Extract the list of toplevel packages associated with a pip install."""
  # Account for default installations and --user installations (most common).
  # Note: we should possibly also account for --root, --prefix, & -t/--target.
  sitepackages = site.getsitepackages() + [site.getusersitepackages()]
  for package in _extract_installed_packages(pip_output):
    infodir = _get_distinfo_path(package, sitepackages)
    if not infodir:
      continue
    toplevel = os.path.join(infodir, "top_level.txt")
    if not os.path.exists(toplevel):
      continue
    for line in open(toplevel):
      line = line.strip()
      if line:
        yield line


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
        _COLAB_DATA_MIMETYPE, ({
            "pip_warning": {
                "packages": packages,
            }
        },),
        raw=True)
