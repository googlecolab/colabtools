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
"""Custom Jupyter ContentsManager."""

import os

import notebook.transutils as _  # must import before below to prevent NameError
# pylint: disable=g-bad-import-order
from notebook.services.contents import largefilemanager
import traitlets


class ColabFileContentsManager(largefilemanager.LargeFileManager):
  """Class that extends Jupyter's FileContentsManager to include file size."""

  # TODO(b/124535699): can be removed after updating jupyter/notebook to >=5.5.0
  # pylint: disable=g-line-too-long
  # From https://github.com/jupyter/notebook/commit/174e72417493a7eb5ab5db0a9d99df0a4b0acb09

  @traitlets.default('delete_to_trash')
  def _default_delete_to_trash(self):
    return False

  # pylint: disable=redefined-builtin
  def get(self, path, content=True, type=None, format=None):
    model = super(ColabFileContentsManager, self).get(path, content, type,
                                                      format)
    if 'size' not in model:
      # Populate file size.
      os_path = self._get_os_path(path)
      info = os.lstat(os_path)

      try:
        size = info.st_size
      except (ValueError, OSError):
        self.log.warning('Unable to get size.')
        size = None

      model['size'] = size
    return model
