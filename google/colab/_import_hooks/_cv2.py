# Copyright 2018 Google Inc. All rights reserved.
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
"""Import hook to disable cv.imshow() and cv2.imshow() within Colab."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import functools
import imp
import logging
import os
import sys


class DisabledFunctionError(ValueError):
  """Error raised when user attempts to call a disabled function."""

  def __init__(self, message, funcname=None, **kwargs):
    super(DisabledFunctionError, self).__init__(message, **kwargs)
    self.funcname = funcname


def disable_function(func, reason, env_var, name=None):
  """Wrapper that prevents a user from calling a function.

  Args:
    func : The function to wrap & disable.
    reason : The user-facing explanation for why this function is disabled.
    env_var : The name of the environment variable that can optionally be used
      to re-enable the function.
    name : The function name to use within the error message.

  Returns:
    wrapped : the wrapped function
  """
  message = """
{name} is disabled in Colab: {reason}
If you would like to re-enable this function, first run:
  import os
  os.environ["{env_var}"] = 'true'
""".format(
    name=name or func.__name__, reason=reason, env_var=env_var)

  @functools.wraps(func)
  def wrapped(*args, **kwargs):
    if not os.environ.get(env_var, False):
      raise DisabledFunctionError(message, name or func.__name__)
    return func(*args, **kwargs)

  return wrapped


class _OpenCVImportHook(object):
  """Disables cv.imshow() and cv2.imshow() on import of cv or cv2."""

  reason = (
      '\nRunning {}.imshow causes jupyter sessions to crash;'
      '\nfor details see https://github.com/jupyter/notebook/issues/3935.')
  env_var = 'ENABLE_CV2_IMSHOW'

  def find_module(self, fullname, path=None):
    if fullname not in ['cv', 'cv2']:
      return None
    self.path = path
    return self

  def load_module(self, name):
    """Loads cv/cv2 normally and runs pre-initialization code."""
    previously_loaded = name in sys.modules

    module_info = imp.find_module(name, self.path)
    cv_module = imp.load_module(name, *module_info)

    if not previously_loaded:
      try:
        cv_module.imshow = disable_function(cv_module.imshow,
                                            self.reason.format(name),
                                            self.env_var,
                                            '{}.imshow'.format(name))
      except:  # pylint: disable=bare-except
        logging.exception('Error disabling cv2.imshow().')
        os.environ['COLAB_CV2_IMPORT_HOOK_EXCEPTION'] = '1'

    return cv_module


def _register_hook():
  sys.meta_path = [_OpenCVImportHook()] + sys.meta_path
