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
"""Custom IPython EventManager."""

from __future__ import print_function

import IPython.core.events as events


class ColabEventManager(events.EventManager):
  """Class that extends Jupyter's FileContentsManager to include file size."""

  # TODO(b/124535699): can be removed after updating ipython/ipython past #11639
  def trigger(self, event, *args, **kwargs):
    for func in self.callbacks[event][:]:
      try:
        func(*args, **kwargs)
      except (Exception, KeyboardInterrupt):  # pylint: disable=broad-except
        print("Error in callback {} (for {}):".format(func, event))
        self.shell.showtraceback()
