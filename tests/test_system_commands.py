# -*- encoding: utf-8 -*
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
"""Tests for the google.colab._system_commands package."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import threading
import time
import unittest

import IPython
from IPython.core import interactiveshell
from IPython.utils import io
import pytest
import six
from google.colab import _system_commands


class SystemCommandsTest(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    ipython = interactiveshell.InteractiveShell.instance()
    ipython.kernel = object()
    cls.ip = IPython.get_ipython()
    cls.orig_pty_max_read_bytes = _system_commands._PTY_READ_MAX_BYTES_FOR_TEST

  def setUp(self):
    self.ip.reset()
    _system_commands._PTY_READ_MAX_BYTES_FOR_TEST = self.orig_pty_max_read_bytes

  def testSubprocessStdoutCaptured(self):
    captured_output = self.run_cell('r = %shell echo "hello world"')

    self.assertEqual('', captured_output.stderr)
    self.assertEqual('hello world\n', captured_output.stdout)
    result = self.ip.user_ns['r']
    self.assertEqual(0, result.returncode)
    self.assertEqual('hello world\n', result.output)

  def testSubprocessStderrCaptured(self):
    captured_output = self.run_cell('r = %shell echo "hello world" 1>&2')

    self.assertEqual('hello world\n', captured_output.stderr)
    self.assertEqual('', captured_output.stdout)
    result = self.ip.user_ns['r']
    self.assertEqual(0, result.returncode)
    self.assertEqual('hello world\n', result.output)

  def testStdinEchoTurnedOff(self):
    # The -s flag for read disables terminal echoing.
    cmd = 'r = %shell /bin/bash -c \'read -s res && echo "You typed: $res"\''
    captured_output = self.run_cell(cmd, provided_input='cats\n')

    self.assertEqual('', captured_output.stderr)
    self.assertEqual('You typed: cats\n', captured_output.stdout)
    result = self.ip.user_ns['r']
    self.assertEqual(0, result.returncode)
    self.assertEqual('You typed: cats\n', result.output)

  def testStdinRequired(self):
    captured_output = self.run_cell(
        'r = %shell read result && echo "You typed: $result"',
        provided_input='cats\n')

    self.assertEqual('', captured_output.stderr)
    self.assertEqual('cats\nYou typed: cats\n', captured_output.stdout)
    result = self.ip.user_ns['r']
    self.assertEqual(0, result.returncode)
    self.assertEqual('cats\nYou typed: cats\n', result.output)

  def testMoreInputThanReadBySubprocessIsDiscarded(self):
    # Normally, read will read characters until a newline is encountered. The
    # -n flag causes it to return after reading a specified number of characters
    # or a newline is encountered, whichever comes first.
    captured_output = self.run_cell(
        'r = %shell /bin/bash -c \'read -n1 char && echo "You typed: $char"\'',
        provided_input='cats\n')

    self.assertEqual('', captured_output.stderr)
    # TODO(b/36984411): Isolate why a carriage return is being emitted for the
    # additional input.
    self.assertEqual('cats\r\nYou typed: c\n', captured_output.stdout)
    result = self.ip.user_ns['r']
    self.assertEqual(0, result.returncode)
    self.assertEqual('cats\r\nYou typed: c\n', result.output)

  def testSubprocessHasPTY(self):
    captured_output = self.run_cell('r = %shell tty')

    self.assertEqual('', captured_output.stderr)
    self.assertIn('/dev/pts/', captured_output.stdout)
    result = self.ip.user_ns['r']
    self.assertEqual(result.returncode, 0)

  def testErrorPropagatesByDefault(self):
    captured_output = self.run_cell("""
import subprocess
try:
  %shell /bin/false
except subprocess.CalledProcessError as e:
  caught_exception = e
""")

    self.assertEqual('', captured_output.stderr)
    self.assertEqual('', captured_output.stdout)
    result = self.ip.user_ns['caught_exception']
    self.assertEqual(1, result.returncode)
    self.assertEqual('', result.output)

  def testIgnoreErrorsDoesNotPropagate(self):
    captured_output = self.run_cell("""
%%shell --ignore-errors
/bin/false
""")

    self.assertEqual('', captured_output.stderr)
    # TODO(b/36984411): IPython prints a prompt string when the result of a cell
    # invocation is an object whose __repr__ returns ''.
    self.assertIn(captured_output.stdout, ('', 'Out[1]: \n'))
    result = self.ip.user_ns['_']
    self.assertEqual(1, result.returncode)
    self.assertEqual('', result.output)

  def testLargeOutputWrittenAndImmediatelyClosed(self):
    _system_commands._PTY_READ_MAX_BYTES_FOR_TEST = 1
    captured_output = self.run_cell(
        'r = %shell /bin/bash -c "printf \'%0.s-\' {1..100}"')

    self.assertEqual('', captured_output.stderr)
    self.assertEqual(100, len(captured_output.stdout))
    result = self.ip.user_ns['r']
    self.assertEqual(0, result.returncode)

  @pytest.mark.skipif(
      six.PY3,
      reason=('TODO(b/36984411): Currently, unicode characters '
              'in output are not properly decoded for Python '
              '3.'))
  def testUnicodeInput(self):
    # TODO(b/36984411): Also add testing for unicode characters in the provided
    # command.

    # "猫" is "cats" in simplified Chinese.
    cmd = u'r = %shell read result && echo "You typed: $result"'
    captured_output = self.run_cell(cmd, provided_input=u'猫\n')

    self.assertEqual('', captured_output.stderr)
    self.assertEqual('猫\nYou typed: 猫\n', captured_output.stdout)
    result = self.ip.user_ns['r']
    self.assertEqual(0, result.returncode)
    self.assertEqual('猫\nYou typed: 猫\n', result.output)

  def run_cell(self, cell_contents, provided_input=None):
    """Execute the cell contents, optionally providing input to the subprocess.

    Args:
      cell_contents: Code to execute.
      provided_input: Input provided to the executing shell magic.

    Returns:
      Captured IPython output during execution.
    """

    # Why execute in a separate thread? The shell magic blocks until the
    # process completes, even if it is blocking on input. As such, we need to
    # asynchronously provide input by periodically popping the content and
    # forwarding it to the subprocess.
    def worker(inputs, result_container):
      magic = _system_commands._ShellMagics(
          self.ip, read_stdin_message=lambda: inputs.pop(0) if inputs else None)

      self.ip.register_magics(magic)

      with io.capture_output() as captured:
        self.ip.run_cell(cell_contents)

      result_container['output'] = captured

    result = {}
    input_queue = []
    t = threading.Thread(
        target=worker, args=(
            input_queue,
            result,
        ))
    t.daemon = True
    t.start()

    if provided_input is not None:
      time.sleep(2)
      input_queue.append(provided_input)

    t.join(30)
    self.assertFalse(t.is_alive())

    return result['output']
