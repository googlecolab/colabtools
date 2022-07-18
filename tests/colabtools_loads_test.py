"""Tests that colabtools loads."""

import unittest

import google.colab


class ColabtoolsLoadsTest(unittest.TestCase):

  def testSomethingBasic(self):
    self.assertIn('auth', dir(google.colab))
