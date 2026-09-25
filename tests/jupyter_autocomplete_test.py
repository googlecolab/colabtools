"""Smoke tests for autocomplete customizations.

IPython changed and these tests are reading IPython directly: they call the
completer rather than Colab's `complete_request` handler, so they track
IPython's own output shape. Fuller end-to-end coverage of user-visible
autocomplete lives in the Google-internal integration notebooks.
"""

import os
import subprocess
import sys
import unittest


def _splice_expr(code, cursor_pos):
  """Returns an expr splicing completions of `code` at `cursor_pos`."""
  # One line because `jupyter console` reads stdin line-by-line.
  return (
      'print([{code!r}[:c.start] + c.text + {code!r}[c.end:] '
      'for c in get_ipython().Completer.completions({code!r}, {pos})])'
  ).format(code=code, pos=cursor_pos)


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
    # Splices matches; see `requalify_attribute_matches` in _completion.py.
    output = _run_under_jupyter([
        'import getpass',
        'import warnings',
        # IPython filters ProvisionalCompleterWarning to "error" at import.
        'warnings.simplefilter("ignore")',
        _splice_expr('getpass.getp', 12),
    ])
    self.assertIn("'getpass.getpass'", output)

  def testInlineAutocomplete(self):
    """Test that autocomplete works inside another expression."""
    output = _run_under_jupyter([
        'import os',
        'import warnings',
        'warnings.simplefilter("ignore")',
        _splice_expr('help(os.)', 8),
    ])
    self.assertIn("'help(os.abort)'", output)

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
