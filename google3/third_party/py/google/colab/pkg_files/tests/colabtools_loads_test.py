"""Tests that colabtools loads."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import unittest

import google.colab


class ColabtoolsLoadsTest(unittest.TestCase):

  def testSomethingBasic(self):
    self.assertIn('auth', dir(google.colab))
