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
"""Custom Jupyter FilesHandler."""

from notebook.base import handlers


class ColabAuthenticatedFileHandler(handlers.AuthenticatedFileHandler):

  def set_extra_headers(self, path):
    super(ColabAuthenticatedFileHandler, self).set_extra_headers(path)
    # The Content-Length header may be removed by upstream proxies (e.g. using
    # Transfer-Encoding=chunked). As such, we explicitly set a header containing
    # the size so that clients have the ability to show progress.
    size = self.get_content_size()
    if size:
      self.add_header('X-File-Size', size)
