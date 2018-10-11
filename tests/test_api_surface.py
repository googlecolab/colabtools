"""Test that our definition of the API for modules in google.colab is correct.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import unittest

import google.colab


class ApiTest(unittest.TestCase):

  def testAll(self):
    # Check that __all__ is a subset of dir. If it is not, then someone has made
    # a typo in defining __all__.
    self.assertLess(set(google.colab.__all__), set(dir(google.colab)))

  def testTopLevelSubmodules(self):
    # Check that __all__ is a subset of dir for each module in
    # google.colab.__all__
    for module_name in google.colab.__all__:
      module = google.colab.__dict__[module_name]
      # No __all__ only allowed for __init__s.
      is_init = '__init__.py' in os.path.basename(module.__file__)
      has_all = hasattr(module, '__all__')
      if is_init and not has_all:
        continue
      self.assertTrue(has_all, 'No __all__ in ' + module.__name__)
      self.assertLess(
          set(module.__all__), set(dir(module)),
          '__all__ contains name not in dir(module) for ' + module.__name__)
