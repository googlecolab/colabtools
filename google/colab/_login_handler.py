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
"""Customized login handler for Colab."""

from notebook.auth import login


class ColabLoginHandler(login.LoginHandler):

  @classmethod
  def validate_security(cls, *args, **kwargs):
    # We handle Colab's security separate from the Jupyter login mechanism; we
    # override this class to avoid spurious logging.
    pass
