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
"""Tests for google.colab.data_table."""

import unittest
import IPython

import pandas as pd

from google.colab import data_table

#  pylint:disable=g-import-not-at-top
try:
  from unittest import mock  #  pylint:disable=g-importing-member
except ImportError:
  import mock
#  pylint:enable=g-import-not-at-top


class DataTableTest(unittest.TestCase):

  def setUp(self):
    super(DataTableTest, self).setUp()
    self.ip_patcher = mock.patch.object(IPython, 'get_ipython', autospec=True)
    get_ipython = self.ip_patcher.start()
    get_ipython.return_value = IPython.InteractiveShell()

  def tearDown(self):
    self.ip_patcher.stop()
    super(DataTableTest, self).tearDown()

  def testDataTable(self):
    df = pd.DataFrame({
        'x': [12345, 23456, 34567],
        'y': ['abcde', 'bcdef', 'cdefg']
    })

    dt = data_table.DataTable(df)
    html = dt._repr_html_()
    for col in df.columns:
      for val in df[col]:
        self.assertIn('{}'.format(val), html)

  def testFormatterEnableDisable(self):

    def get_formatter():
      key = data_table._JAVASCRIPT_MODULE_MIME_TYPE
      formatters = IPython.get_ipython().display_formatter.formatters
      if key in formatters:
        return formatters[key].for_type_by_name('pandas.core.frame',
                                                'DataFrame')
      else:
        return None

    # default formatter is None.
    self.assertIsNone(get_formatter())

    # enabling changes the formatter.
    data_table.enable_dataframe_formatter()
    # classmethod identity is not preserved; compare reprs:
    self.assertEqual(
        repr(get_formatter()), repr(data_table.DataTable.formatter))

    # disabling restores the default.
    data_table.disable_dataframe_formatter()
    self.assertIsNone(get_formatter())
