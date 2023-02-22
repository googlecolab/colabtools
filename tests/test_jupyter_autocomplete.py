"""Smoke tests for autocomplete customizations."""

import os
import subprocess
import sys
import unittest


def _run_under_jupyter(code_lines):
  with open('jupyter_code', 'w') as f:
    f.write('\n'.join(code_lines))

  command = 'cat jupyter_code | jupyter console --simple-prompt --kernel='
  kernel = 'python{}'.format(sys.version_info[0])
  # Clear PYTHONPATH to ignore any path munging done in _tensorflow_magics.
  # In the real container, Jupyter is not subject to path changes anyway.
  output = subprocess.check_output(
      command + kernel, shell=True, env={'PYTHONPATH': ''}
  )
  # subprocess output comes back as bytes, but we convert to unicode for easier
  # comparison.
  return output.decode('utf8')


@unittest.skipIf(
    os.environ.get('SKIP_JUPYTER_AUTOCOMPLETE', ''),
    'Skipping this test outside of full VM.',
)
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

  def testTypeAnnotations(self):
    output = _run_under_jupyter([
        'from ipykernel.jsonutil import json_clean',
        'def the_function(msg: str="here") -> str: pass',
        'result = get_ipython().kernel.do_inspect("the_function", 1, 0)',
        'json_clean(result)',
    ])
    self.assertIn('the_function', output)
