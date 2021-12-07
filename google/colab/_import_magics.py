# Copyright 2020 Google Inc.
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
"""Allow magics to be declared without forcing an import.

This module allows us to declare a magic will be available while delaying the
import of the associated package. The primary purpose is to avoid importing too
many packages at startup, as it complicates package installation for users.

Note that importing the original module will *replace* these registrations, as
magics are still being registered in their original modules.

In addition, the IPython getdoc() function allows us to lazily request help on
a magic -- again, requesting help on a specific magic will import the module
where that magic resides.

For general Python objects or functions, this might be dangerous -- however,
magics are special, in that they're not represented by a Python object, so
there's no danger that overwriting the name -> function mapping will cause
trouble later on. The only user-visible aspect is that the source reference in
the help will update from this module to the actual importing module after the
first use.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import sys

# IPython requires get_ipython to be available as a local variable wherever you
# want to register a magic, in an attempt to prevent you from registering
# magics before the IPython magic machinery is loaded. So we need to directly
# import the symbol, instead of just the module.
from IPython import get_ipython
from IPython.core import magic


def _load_extension(module):
  get_ipython().extension_manager.load_extension(module)


def _get_extension_magic(name, module, magic_type, magic_module_loader):
  magic_module_loader(module)
  m = get_ipython().magics_manager.magics[magic_type][name]
  if m.__module__ == __name__:
    raise ValueError('No %s magic named "%s" found in "%s"' %
                     (magic_type, name, module))
  return m


def _declare_line_magic(name, module, magic_module_loader):
  """Declare a line magic called name in module."""
  # If the module or extension has already been imported, don't overwrite the
  # existing definition.
  if module in sys.modules or module in get_ipython().extension_manager.loaded:
    return

  def impl(line, **kwargs):
    return _get_extension_magic(name, module, 'line',
                                magic_module_loader)(line, **kwargs)

  # pylint: disable=g-long-lambda
  impl.getdoc = lambda: _get_extension_magic(name, module, 'line',
                                             magic_module_loader).__doc__
  magic.register_line_magic(name)(impl)


def _declare_cell_magic(name, module, magic_module_loader):
  """Declare a cell magic called name in module."""
  # If the module or extension has already been imported, don't overwrite the
  # existing definition.
  if module in sys.modules or module in get_ipython().extension_manager.loaded:
    return

  def impl(line, cell, **kwargs):
    return _get_extension_magic(name, module, 'cell',
                                magic_module_loader)(line, cell, **kwargs)

  # pylint: disable=g-long-lambda
  impl.getdoc = lambda: _get_extension_magic(name, module, 'cell',
                                             magic_module_loader).__doc__
  magic.register_cell_magic(name)(impl)


def _declare_colabx_magics():
  if get_ipython():
    _declare_cell_magic('bigquery', 'google.cloud.bigquery', _load_extension)
