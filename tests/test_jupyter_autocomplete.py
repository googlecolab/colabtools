"""Smoke tests for autocomplete customizations."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import subprocess
import unittest

from six.moves import shlex_quote


class JupyterAutocompleteTest(unittest.TestCase):

  @unittest.skipIf(
      os.environ.get('TRAVIS', '') == 'true',
      'Skipping this test on Travis CI.')
  def testBasicAutocompletions(self):
    py_command = shlex_quote('; '.join([
        'import getpass',
        'print(get_ipython().complete("", "getpass.getp", 12)[1])',
    ]))
    command = 'echo {} | jupyter console --simple-prompt --kernel='.format(
        py_command)
    for kernel in ('python2', 'python3'):
      output = subprocess.check_output(command + kernel, shell=True)
      self.assertIn("'getpass.getpass'", output.decode('utf8'))
