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
"""Import hook for the upcoming tensorflow default switch on package import."""

import imp
import sys
from IPython import display
from google.colab import _tensorflow_magics


class _TensorflowImportHook(object):
  """Notifies the user of the impending TensorFlow upgrade on imporee."""

  def find_module(self, fullname, path=None):
    if fullname != 'tensorflow':
      return None
    self.module_info = imp.find_module(fullname.split('.')[-1], path)
    return self

  def load_module(self, fullname):
    """Loads Tensorflow normally and emits a notification."""
    previously_loaded = fullname in sys.modules
    tf_module = imp.load_module(fullname, *self.module_info)

    if (tf_module.__version__.startswith('1') and
        not _tensorflow_magics.explicitly_set() and not previously_loaded):
      display.display(
          display.HTML("""<p style="color: red;">
The default version of TensorFlow in Colab will soon switch to TensorFlow 2.x.<br>
We recommend you <a href="https://www.tensorflow.org/guide/migrate" target="_blank">upgrade</a> now 
or ensure your notebook will continue to use TensorFlow 1.x via the <code>%tensorflow_version 1.x</code> magic:
<a href="https://colab.research.google.com/notebooks/tensorflow_version.ipynb" target="_blank">more info</a>.</p>
"""))
    return tf_module


def _register_hook():
  sys.meta_path = [_TensorflowImportHook()] + sys.meta_path
