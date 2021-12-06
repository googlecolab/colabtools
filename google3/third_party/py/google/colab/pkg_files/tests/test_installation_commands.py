# -*- coding: utf-8 -*-
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
"""Tests for the google.colab._installation_commands package."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import sys
import unittest

import IPython
from IPython.utils import io

from google.colab import load_ipython_extension

MOCKED_COMMANDS = {
    'pip install pandas':
        """
Requirement already satisfied: pandas in /usr/local/lib/python2.7/dist-packages (0.22.0)
Requirement already satisfied: pytz>=2011k in /usr/local/lib/python2.7/dist-packages (from pandas) (2018.9)
Requirement already satisfied: python-dateutil in /usr/local/lib/python2.7/dist-packages (from pandas) (2.5.3)
Requirement already satisfied: numpy>=1.9.0 in /usr/local/lib/python2.7/dist-packages (from pandas) (1.16.2)
Requirement already satisfied: six>=1.5 in /usr/local/lib/python2.7/dist-packages (from python-dateutil->pandas) (1.11.0)
""",
    'pip install -U numpy':
        """
Collecting numpy
  Downloading https://files.pythonhosted.org/packages/c4/33/8ec8dcdb4ede5d453047bbdbd01916dbaccdb63e98bba60989718f5f0876/numpy-1.16.2-cp27-cp27mu-manylinux1_x86_64.whl (17.0MB)
    100% |============================| 17.0MB 660kB/s
fastai 0.7.0 has requirement torch<0.4, but you'll have torch 1.0.1.post2 which is incompatible.
albumentations 0.1.12 has requirement imgaug<0.2.7,>=0.2.5, but you'll have imgaug 0.2.8 which is incompatible.
featuretools 0.4.1 has requirement pandas>=0.23.0, but you'll have pandas 0.22.0 which is incompatible.
Installing collected packages: numpy
  Found existing installation: numpy 1.14.6
    Uninstalling numpy-1.14.6:
      Successfully uninstalled numpy-1.14.6
Successfully installed numpy-1.16.2
"""
}


class MockInteractiveShell(IPython.InteractiveShell):
  """Interactive shell that mocks some commands."""

  def system(self, cmd):
    if cmd in MOCKED_COMMANDS:
      sys.stderr.write('')
      sys.stdout.write(MOCKED_COMMANDS[cmd])
      self.user_ns['_exit_code'] = 0
    else:
      return super(MockInteractiveShell, self).system(cmd)


class InstallationCommandsTest(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    super(InstallationCommandsTest, cls).setUpClass()
    cls.ip = MockInteractiveShell()
    load_ipython_extension(cls.ip)

  def testPipMagicPandas(self):
    output = self.run_cell('%pip install pandas')
    self.assertEqual([], output.outputs)
    self.assertEqual('', output.stderr)
    self.assertIn('pandas', output.stdout)

  def testPipMagicNumpy(self):
    output = self.run_cell('%pip install -U numpy')
    self.assertEqual([], output.outputs)
    self.assertEqual('', output.stderr)
    self.assertIn('numpy', output.stdout)

  def run_cell(self, cell_contents):
    with io.capture_output() as captured:
      self.ip.run_cell(cell_contents)
    return captured
