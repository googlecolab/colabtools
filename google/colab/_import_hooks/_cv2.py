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

import functools
import importlib
import logging
import os
import sys

from google.colab._import_hooks._hook_injector import HookInjectorLoader


class DisabledFunctionError(ValueError):
  """Error raised when user attempts to call a disabled function."""

  def __init__(self, message, funcname=None, **kwargs):
    super(DisabledFunctionError, self).__init__(message, **kwargs)
    self.funcname = funcname


def disable_function(func, message, env_var, name=None):
  """Wrapper that prevents a user from calling a function.

  Args:
    func: The function to wrap & disable.
    message: The user-facing explanation for why this function is disabled.
    env_var: The name of the environment variable that can optionally be used to
      re-enable the function.
    name: The function name to use within the error message.

  Returns:
    wrapped: the wrapped function
  """

  @functools.wraps(func)
  def wrapped(*args, **kwargs):
    if not os.environ.get(env_var, False):
      raise DisabledFunctionError(message, name or func.__name__)
    return func(*args, **kwargs)

  wrapped.env_var = env_var

  return wrapped


class _OpenCVImportHook(importlib.abc.MetaPathFinder):
  """Disables cv.imshow() and cv2.imshow() on import of cv or cv2."""

  message = (
      '{0}.imshow() is disabled in Colab, because it causes Jupyter sessions\n'
      'to crash; see https://github.com/jupyter/notebook/issues/3935.\n'
      'As a substitution, consider using\n'
      '  from google.colab.patches import {0}_imshow\n'
  )
  env_var = 'ENABLE_CV2_IMSHOW'

  def find_spec(self, fullname, path=None, target=None):
    """Try to find a spec for cv or cv2 and hook the module loader."""
    if fullname not in ['cv', 'cv2']:
      return None

    def init_code_callback(module, previously_loaded):
      if not previously_loaded:
        try:
          module.imshow = disable_function(
              module.imshow,
              message=self.message.format(fullname),
              env_var=self.env_var,
              name='{}.imshow'.format(fullname),
          )
        except:  # pylint: disable=bare-except
          logging.exception('Error disabling %s.imshow().', fullname)
          os.environ['COLAB_CV2_IMPORT_HOOK_EXCEPTION'] = '1'

    loader = HookInjectorLoader(
        fullname,
        path,
        target,
        type(self),
        init_code_callback,
    )
    # If the module can't be found returning a loader will cause `import cv2` to
    # succeed but with an empty module. Avoid that case by returning None.
    if not loader.find_spec():
      return None
    return importlib.util.spec_from_loader(fullname, loader)


def _register_hook():
  sys.meta_path = [_OpenCVImportHook()] + sys.meta_path
