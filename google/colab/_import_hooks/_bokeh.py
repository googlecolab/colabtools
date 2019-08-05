# Copyright 2019 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Import hook for ensuring that Altair's Colab renderer is registered."""

from __future__ import print_function

import imp
import logging
import os
import sys

import IPython

# Keeps track of the current cell status. It is set to true
# first time enable_bokeh is executed in this cell and flipped
# back to false on post_run_cell.
_bokeh_loaded_in_this_cell = False
_bokeh_resources = None
_bokeh_io_module = None


class _BokehImportHook(object):
  """Configures Bokeh's renderer to support Colab upon import."""

  def find_module(self, fullname, path=None):
    if fullname not in ['bokeh.io']:
      return None
    self.module_info = imp.find_module(fullname.split('.')[-1], path)
    return self

  def load_module(self, name):
    """Loads Bokeh normally and runs pre-initialization code."""
    global _bokeh_io_module

    previously_loaded = name in sys.modules
    _bokeh_io_module = imp.load_module(name, *self.module_info)

    if not previously_loaded:
      try:
        # Overwrite the default 'jupyter' so sample code which uses
        #     from bokeh.io import output_notebook
        #     output_notebook()
        # just works without modification.
        _bokeh_io_module.notebook.install_notebook_hook(
            'jupyter', _load_notebook, _show_doc, _show_app, overwrite=True)
      except:  # pylint: disable=bare-except
        logging.exception('Error enabling Bokeh Colab rendering.')
        os.environ['COLAB_BOKEH_IMPORT_HOOK_EXCEPTION'] = '1'

    return _bokeh_io_module


def _register_hook():
  sys.meta_path = [_BokehImportHook()] + sys.meta_path


def _post_execute():
  global _bokeh_loaded_in_this_cell
  _bokeh_loaded_in_this_cell = False
  IPython.get_ipython().events.unregister('post_run_cell', _post_execute)  # pylint: disable=undefined-variable


def _show_doc(obj, state, notebook_handle):
  """Show the Bokeh plot."""
  global _bokeh_loaded_in_this_cell
  # Load Bokeh into the outputframe if it has not been loaded yet.
  if not _bokeh_loaded_in_this_cell:
    _bokeh_loaded_in_this_cell = True
    IPython.get_ipython().events.register('post_run_cell', _post_execute)  # pylint: disable=undefined-variable
    _bokeh_io_module.notebook.load_notebook(
        resources=_bokeh_resources, hide_banner=True)

  # Call the default bokeh rendering path.
  return _bokeh_io_module.notebook.show_doc(obj, state, notebook_handle)


# pylint: disable=unused-argument
def _load_notebook(resources=None,
                   verbose=False,
                   hide_banner=False,
                   load_timeout=5000):
  global _bokeh_resources
  # In Jupyter this method is called once per notebook launch but with Colab's
  # isolated outputframes this loading needs to be done for each outputframe.
  _bokeh_resources = resources


def _show_app(app, state, notebook_url, port=0, **kw):
  print('Bokeh show_app is currently unsupported')
