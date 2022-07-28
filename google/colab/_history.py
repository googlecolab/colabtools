# Copyright 2020 Google Inc.
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
"""Colab-specific IPython.core.history.HistoryManager."""

import hashlib
import json
import time
from IPython import display
from IPython.core import history


class ColabHistoryManager(history.HistoryManager):
  """Colab-specific history manager to store cell IDs with executions.

  This allows us to associate code executions with the cell which was executed
  in Colab's UI.
  """
  _input_hist_cells = [{'code': '', 'cell_id': '', 'start_time': 0}]

  def reset(self, new_session=True):
    super(ColabHistoryManager, self).reset(new_session=new_session)
    if new_session:
      self._input_hist_cells[:] = [{'code': '', 'cell_id': '', 'start_time': 0}]

  def store_inputs(self, line_num, source, source_raw=None):
    """Variant of HistoryManager.store_inputs which also stores the cell ID."""
    super(ColabHistoryManager, self).store_inputs(
        line_num, source, source_raw=source_raw)

    # The parent_header on the shell is the message that resulted in the code
    # execution request. Grab the cell ID out of that.
    cell_id = self.shell.parent_header.get('metadata',
                                           {}).get('colab', {}).get('cell_id')

    self._input_hist_cells.append({
        'code': source_raw,
        'cell_id': cell_id,
        'start_time': time.time(),
    })

  def _history_with_cells_as_json(self):
    """Utility accessor to allow frontends an expression to fetch history.

    Returns:
      A Javascript display object with the execution history.
    """
    # To be able to access the raw string as an expression we need to transfer
    # the plain string rather than the quoted string representation. The
    # Javascript display wrapper is used for that.
    return display.Javascript(json.dumps(self._input_hist_cells))

  def _executed_cells_as_json(self, include_source_hash=False):
    """Provides frontends an expression to fetch previously executed cells.

    Args:
      include_source_hash: If true, include a hash of the code that ran.

    Returns:
      A Javascript display object of a dict of the executed cell IDs to their
      execution index. If include_source was specified, the items in the dict
      are dicts with 'executionCount' and 'sourceHash' fields.
    """
    cells = dict()
    for i, cell in enumerate(self._input_hist_cells):
      if include_source_hash:
        # LINT.IfChange(execution_count)
        cells[cell['cell_id']] = {
            'executionCount':
                i,
            'sourceHash':
                hashlib.md5(cell['code'].encode('utf8')).hexdigest()[:10]
        }
        # LINT.ThenChange()
      else:
        cells[cell['cell_id']] = i
    # To be able to access the raw string as an expression we need to transfer
    # the plain string rather than the quoted string representation. The
    # Javascript display wrapper is used for that.
    return display.Javascript(json.dumps(cells))
