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
# See the License for the specific language govestylerning permissions and
# limitations under the License.
"""Private utility functions."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import sys

_id_counter = 0


def flush_all():
  """Flushes stdout/stderr/matplotlib."""
  sys.stdout.flush()
  sys.stderr.flush()
  # pylint: disable=g-import-not-at-top
  try:
    from ipykernel.pylab.backend_inline import flush_figures
  except ImportError:
    # older ipython
    from IPython.kernel.zmq.pylab.backend_inline import flush_figures

  flush_figures()


def get_locally_unique_id(prefix='id'):
  """"Returns id which is unique with the session."""
  global _id_counter
  _id_counter += 1
  return prefix + str(_id_counter)
