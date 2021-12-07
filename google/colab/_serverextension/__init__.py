# Copyright 2018 Google Inc.
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
"""Colab-specific Jupyter serverextensions."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import logging
import os
import shlex
import subprocess


def _subprocess_check_output(args, *posargs, **kwargs):
  """subprocess.check_output wrapper for colab.

  This provides a hook for colab to prefix the command to be executed, to allow
  us to run all subcommands under another program (eg timeout) or in another
  docker container.

  Args:
    args: the command to execute, as a string or list of strings.
    *posargs: additional positional arguments to subprocess.check_output.
    **kwargs: additional keywords arguments to subprocess.check_output.

  Returns:
    The output from running the command.
  """
  args_prefix = os.environ.get('COLAB_SERVEREXTENSION_SUBPROCESS_PREFIX', '')
  if args_prefix:
    if isinstance(args, str):
      args = args_prefix + ' ' + args
    else:
      args = shlex.split(args_prefix) + args
  return subprocess.check_output(args, *posargs, **kwargs)


class _ColabLoggingFilter(logging.Filter):

  def filter(self, record):
    # We don't use Jupyter message signing for security, so we disable this
    # message to avoid spurious and confusing logging for users.
    return record.msg != ('Message signing is disabled.  This is insecure and '
                          'not recommended!')


def _jupyter_server_extension_paths():
  return [{
      'module': 'google.colab._serverextension',
  }]


def load_jupyter_server_extension(nb_server_app):
  """Called by Jupyter when starting the notebook manager."""
  # We only want to import these modules when setting up a server extension, and
  # want to avoid raising an exception when the `notebook` package isn't
  # available.
  # pylint: disable=g-import-not-at-top
  from notebook import utils
  from google.colab._serverextension import _handlers
  # pylint: enable=g-import-not-at-top

  nb_server_app.log.addFilter(_ColabLoggingFilter())
  app = nb_server_app.web_app

  url_maker = lambda path: utils.url_path_join(app.settings['base_url'], path)
  monitor_relative_path = '/api/colab/resources'

  app.add_handlers('.*$', [
      (url_maker(monitor_relative_path), _handlers.ResourceUsageHandler, {
          'kernel_manager': app.settings['kernel_manager']
      }),
      (url_maker('/api/colab/drive'), _handlers.DriveHandler),
  ])
  nb_server_app.log.info('google.colab serverextension initialized.')
