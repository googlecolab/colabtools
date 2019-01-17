"""Smoke tests for autocomplete customizations."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import subprocess
import sys
import unittest

from six.moves import shlex_quote


def _run_under_jupyter(code_lines):
  command = 'echo {} | jupyter console --simple-prompt --kernel='.format(
      shlex_quote('; '.join(code_lines)))
  kernel = 'python{}'.format(sys.version_info[0])
  output = subprocess.check_output(command + kernel, shell=True)
  # subprocess output comes back as bytes, but we convert to unicode for easier
  # comparison.
  return output.decode('utf8')


@unittest.skipIf(
    os.environ.get('TRAVIS', '') == 'true', 'Skipping this test on Travis CI.')
class JupyterAutocompleteTest(unittest.TestCase):

  def testBasicAutocompletions(self):
    """Test that autocomplete works for a top-level definition."""
    output = _run_under_jupyter([
        'import getpass',
        'print(get_ipython().complete("", "getpass.getp", 12)[1])',
    ])
    self.assertIn("'getpass.getpass'", output)

  def testInlineAutocomplete(self):
    """Test that autocomplete works inside another expression."""
    output = _run_under_jupyter([
        'import os',
        'print(get_ipython().complete("", "help(os.)", 8)[1])',
    ])
    self.assertIn("'os.abort'", output)

  def testDictAutocomplete(self):
    output = _run_under_jupyter([
        'd = {"key": "value"}',
        'print(get_ipython().complete("", "d[", 2)[1])',
    ])
    self.assertIn("'key'", output)
