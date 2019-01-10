"""Smoke tests for autocomplete customizations."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import unittest

from google.colab._autocomplete import _splitter


class AutocompleteTest(unittest.TestCase):

  def testSplit(self):
    self.assertEqual('get', _splitter.split('print(get'))
