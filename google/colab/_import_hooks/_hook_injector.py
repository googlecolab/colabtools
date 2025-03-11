# Copyright 2025 Google Inc. All rights reserved.
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
"""Custom loader that calls a callback upon import."""
import importlib
import sys


class HookInjectorLoader(importlib.abc.Loader):
  """Custom loader that calls a callback upon import."""

  def __init__(
      self,
      fullname,
      path,
      target,
      meta_path_finder_cls,
      init_code_callback,
  ):
    self.fullname = fullname
    self.path = path
    self.target = target
    self.previously_loaded = self.fullname in sys.modules
    self.meta_path_finder_cls = meta_path_finder_cls
    self.init_code_callback = init_code_callback

  def create_module(self, spec):
    module = None
    loader = None
    for meta_path in sys.meta_path:
      if not isinstance(meta_path, self.meta_path_finder_cls) and hasattr(
          meta_path, 'find_spec'
      ):
        spec = meta_path.find_spec(self.fullname, self.path, self.target)
        if spec is not None:
          loader = spec.loader
          module = importlib.util.module_from_spec(spec)
          sys.modules[self.fullname] = module
          break

    if module is not None and loader is not None:
      spec.loader.exec_module(module)
      self.init_code_callback(module, self.previously_loaded)

    return module

  def exec_module(self, module):
    pass
