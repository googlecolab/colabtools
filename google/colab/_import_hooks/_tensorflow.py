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
"""Import hook for ensuring that TensorFlow uses allow_growth by default."""

import datetime
import imp
import logging
import os
import sys


class _TensorFlowImportHook(object):
  """Runs a session with allow_growth=true so TF doesn't grab all GPU memory.

  By default, the majority of GPU memory will be allocated by the first
  execution of a TensorFlow graph. While this behavior can be desirable for
  production pipelines, it is less desirable for interactive use. The
  allow_growth setting attempts to only allocate GPU memory as needed:
    https://www.tensorflow.org/guide/using_gpu#allowing_gpu_memory_growth

  Note: The allow_growth setting outlasts the created session and subsequent
  graph executions only allocate GPU memory as needed.
  """

  def __init__(self, module_name):
    """Initialize the import hook.

    Args:
      module_name: Name of the tensorflow to install the import hook for. Only
        exposed for testing.
    """
    self.__module_name = module_name

  def find_module(self, fullname, path=None):
    if (fullname != self.__module_name or
        os.getenv('DISABLE_COLAB_TF_IMPORT_HOOK') or not self._has_gpu()):
      return None
    self.path = path
    return self

  def load_module(self, name):
    """Loads TensorFlow normally and runs pre-initialization code."""
    previously_loaded = name in sys.modules

    module_info = imp.find_module(name, self.path)
    tf_module = imp.load_module(name, *module_info)

    if not previously_loaded:
      start_time = datetime.datetime.now()
      try:
        config = tf_module.ConfigProto(
            gpu_options=tf_module.GPUOptions(allow_growth=True))
        with tf_module.Session(config=config):
          pass
        # Record the startup duration to help diagnose whether this import hook
        # is contributing to slow imports.
        os.environ['COLAB_TF_IMPORT_HOOK_STARTUP_DURATION'] = str(
            (datetime.datetime.now() - start_time).total_seconds())
      except:  # pylint: disable=bare-except
        logging.exception('Error running TensorFlow session.')
        os.environ['COLAB_TF_IMPORT_HOOK_EXCEPTION'] = '1'

    return tf_module

  def _has_gpu(self):
    return os.path.exists('/dev/nvidia0')


def _register_hook(module_name='tensorflow'):
  sys.meta_path = [_TensorFlowImportHook(module_name)] + sys.meta_path
