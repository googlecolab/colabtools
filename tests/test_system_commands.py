# -*- encoding: utf-8 -*-
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

import collections
import contextlib
import os
import signal
import textwrap
import threading
import time
import unittest

import IPython
from IPython.core import interactiveshell
from IPython.lib import pretty
from IPython.utils import io

import six

from google.colab import _ipython
from google.colab import _message
from google.colab import _system_commands

#  pylint:disable=g-import-not-at-top
try:
  from unittest import mock
except ImportError:
  import mock
#  pylint:enable=g-import-not-at-top


class FakeShell(interactiveshell.InteractiveShell):

  def system(self, *args, **kwargs):
    return _system_commands._system_compat(self, *args, **kwargs)

  def getoutput(self, *args, **kwargs):
    return _system_commands._getoutput_compat(self, *args, **kwargs)


RunCellWithUpdateCaptureResult = collections.namedtuple(
    'RunCellWithUpdateCaptureResult', ('output', 'update_calls'))


class SystemCommandsTest(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    ipython = FakeShell.instance()
    ipython.kernel = mock.Mock()
    cls.ip = IPython.get_ipython()

    cls.orig_pty_max_read_bytes = _system_commands._PTY_READ_MAX_BYTES_FOR_TEST
    cls.orig_lc_all = os.environ.get('LC_ALL')

  def setUp(self):
    self.ip.reset()
    _system_commands._PTY_READ_MAX_BYTES_FOR_TEST = self.orig_pty_max_read_bytes
    if self.orig_lc_all is None:
      os.environ.pop('LC_ALL', '')
    else:
      os.environ['LC_ALL'] = self.orig_lc_all

  def testSubprocessOutputCaptured(self):
    captured_output = self.run_cell("""
r = %shell echo -n "hello err, " 1>&2 && echo -n "hello out, " && echo "bye..."
""")

    self.assertEqual('', captured_output.stderr)
    self.assertEqual('hello err, hello out, bye...\n', captured_output.stdout)
    result = self.ip.user_ns['r']
    self.assertEqual(0, result.returncode)
    self.assertEqual('hello err, hello out, bye...\n', result.output)

  def testStdinEchoToggling(self):
    # The -s flag for read disables terminal echoing. First read with echoing
    # enabled, then do a subsequent read with echoing disabled.
    cmd = """
r = %shell read r1 && echo "First: $r1" && read -s r2 && echo "Second: $r2"
"""
    result = self.run_cell_capture_update_calls(
        cmd, provided_inputs=['cats\n', 'dogs\n'])
    captured_output, echo_updater_calls = result.output, result.update_calls

    self.assertEqual('', captured_output.stderr)
    self.assertEqual('cats\nFirst: cats\nSecond: dogs\n',
                     captured_output.stdout)
    result = self.ip.user_ns['r']
    self.assertEqual(0, result.returncode)
    self.assertEqual('cats\nFirst: cats\nSecond: dogs\n', result.output)
    # Updates correspond to:
    # 1) Initial state (i.e. read with terminal echoing enabled)
    # 2) Read call with "-s" option
    # 3) Call to bash echo command.
    self.assertEqual([True, False, True], echo_updater_calls)

  def testStdinRequired(self):
    captured_output = self.run_cell(
        'r = %shell read result && echo "You typed: $result"',
        provided_inputs=['cats\n'])

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
        'r = %shell read -n1 char && echo "You typed: $char"',
        provided_inputs=['cats\n'])

    self.assertEqual('', captured_output.stderr)
    # Bash's read command modifies terminal settings when  the "-n" flag is
    # provided to put the terminal in one-char-at-a-time mode. This
    # unconditionally sets the ONLCR oflag, which causes input echoing to map NL
    # to CR-NL on output:
    # http://git.savannah.gnu.org/cgit/bash.git/tree/lib/sh/shtty.c?id=64447609994bfddeef1061948022c074093e9a9f#n128
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
    captured_output = self.run_cell(
        textwrap.dedent("""
      import subprocess
      try:
        %shell /bin/false
      except subprocess.CalledProcessError as e:
        caught_exception = e
      """))

    self.assertEqual('', captured_output.stderr)
    self.assertEqual('', captured_output.stdout)
    result = self.ip.user_ns['caught_exception']
    self.assertEqual(1, result.returncode)
    self.assertEqual('', result.output)

  def testIgnoreErrorsDoesNotPropagate(self):
    captured_output = self.run_cell(
        textwrap.dedent("""
      %%shell --ignore-errors
      /bin/false
      """))

    self.assertEqual('', captured_output.stderr)
    # IPython displays the result of the last statement executed (unless it is
    # None) with a "Out[1]: " prefix. When using io.capture_output(), older
    # versions of IPython don't appear to capture this prompt in the stdout
    # stream. Due to this, we don't assert anything about the stdout output. If
    # an error is thrown, then accessing the "_" variable will fail.
    result = self.ip.user_ns['_']
    self.assertEqual(1, result.returncode)
    self.assertEqual('', result.output)

  def testLargeOutputWrittenAndImmediatelyClosed(self):
    _system_commands._PTY_READ_MAX_BYTES_FOR_TEST = 1
    captured_output = self.run_cell('r = %shell printf "%0.s-" {1..100}')

    self.assertEqual('', captured_output.stderr)
    self.assertEqual(100, len(captured_output.stdout))
    result = self.ip.user_ns['r']
    self.assertEqual(0, result.returncode)

  def testRunsInBashShell(self):
    # The "BASH" environment variable is set for all bash shells.
    captured_output = self.run_cell('r = %shell echo "$BASH"')

    self.assertEqual('', captured_output.stderr)
    self.assertEqual('/bin/bash\n', captured_output.stdout)
    result = self.ip.user_ns['r']
    self.assertEqual(0, result.returncode)
    self.assertEqual('/bin/bash\n', result.output)

  def testUnicodeCmd(self):
    # "小狗" is "dogs" in simplified Chinese.
    captured_output = self.run_cell(u'r = %shell echo -n "Dogs is 小狗"')

    self.assertEqual('', captured_output.stderr)
    self.assertEqual(u'Dogs is 小狗', captured_output.stdout)
    result = self.ip.user_ns['r']
    self.assertEqual(0, result.returncode)
    self.assertEqual(u'Dogs is 小狗', result.output)

  def testUnicodeInputAndOutput(self):
    # "猫" is "cats" in simplified Chinese and its representation requires
    # three bytes. Force reading only one byte at a time and ensure that the
    # character is preserved.
    _system_commands._PTY_READ_MAX_BYTES_FOR_TEST = 1
    cmd = u'r = %shell read result && echo "You typed: $result"'
    captured_output = self.run_cell(cmd, provided_inputs=[u'猫\n'])

    self.assertEqual('', captured_output.stderr)
    self.assertEqual(u'猫\nYou typed: 猫\n', captured_output.stdout)
    result = self.ip.user_ns['r']
    self.assertEqual(0, result.returncode)
    self.assertEqual(u'猫\nYou typed: 猫\n', result.output)

    # Ensure that ShellResult objects don't have a "pretty" representation. This
    # ensures that no output is printed if the magic is the only statement in
    # the cell.
    self.assertEqual(u'', pretty.pretty(result))

  def testFirstInterruptSendsSigInt(self):
    captured_output = self.run_cell(
        textwrap.dedent("""
      %%shell --ignore-errors
      echo 'Before sleep'
      read -t 600
      echo 'Invalid. Read call should never terminate.'
      """),
        provided_inputs=['interrupt'])

    self.assertEqual('', captured_output.stderr)
    result = self.ip.user_ns['_']
    self.assertEqual(-signal.SIGINT, result.returncode)
    self.assertEqual('Before sleep\n', result.output)

  def testSecondInterruptSendsSigTerm(self):
    captured_output = self.run_cell(
        textwrap.dedent("""
      %%shell --ignore-errors
      # Trapping with an empty command causes the signal to be ignored.
      trap '' SIGINT
      echo 'Before sleep'
      read -t 600
      echo 'Invalid. Read call should never terminate.'
      """),
        provided_inputs=['interrupt', 'interrupt'])

    self.assertEqual('', captured_output.stderr)
    result = self.ip.user_ns['_']
    self.assertEqual(-signal.SIGTERM, result.returncode)
    self.assertEqual('Before sleep\n', result.output)

  def testSecondInterruptSendsSigKillAfterSigterm(self):
    captured_output = self.run_cell(
        textwrap.dedent("""
      %%shell --ignore-errors
      # Trapping with an empty command causes the signal to be ignored.
      trap '' SIGINT SIGTERM
      echo 'Before sleep'
      read -t 600
      echo 'Invalid. Read call should never terminate.'
      """),
        provided_inputs=['interrupt', 'interrupt'])

    self.assertEqual('', captured_output.stderr)
    result = self.ip.user_ns['_']
    self.assertEqual(-signal.SIGKILL, result.returncode)
    self.assertEqual('Before sleep\n', result.output)

  def testNonUtf8Locale(self):
    # The "C" locale uses the US-ASCII 7-bit character set.
    os.environ['LC_ALL'] = 'C'

    captured_output = self.run_cell(
        textwrap.dedent("""
      import subprocess
      try:
        %shell echo "should fail"
      except NotImplementedError as e:
        caught_exception = e
      """))

    self.assertEqual('', captured_output.stderr)
    self.assertEqual('', captured_output.stdout)
    self.assertIsNotNone(self.ip.user_ns['caught_exception'])

  def testSystemCompat(self):
    _system_commands._PTY_READ_MAX_BYTES_FOR_TEST = 1
    # "猫" is "cats" in simplified Chinese.
    captured_output = self.run_cell(
        '!read res && echo "You typed: $res"', provided_inputs=[u'猫\n'])

    self.assertEqual('', captured_output.stderr)
    self.assertEqual(u'猫\nYou typed: 猫\n', captured_output.stdout)
    self.assertEqual(0, self.ip.user_ns['_exit_code'])
    self.assertNotIn('_', self.ip.user_ns)

  def testSystemCompatWithInterrupt(self):
    captured_output = self.run_cell('!read res', provided_inputs=['interrupt'])

    self.assertEqual('', captured_output.stderr)
    self.assertEqual(u'^C\n', captured_output.stdout)
    self.assertEqual(-signal.SIGINT, self.ip.user_ns['_exit_code'])
    self.assertNotIn('_', self.ip.user_ns)

  def testSystemCompatWithVarExpansion(self):
    cmd = textwrap.dedent(u"""
      def some_func():
        local_var = 'Hello there'
        !echo "{local_var}"
      some_func()
      """)
    captured_output = self.run_cell(cmd, provided_inputs=[])

    self.assertEqual('', captured_output.stderr)
    self.assertEqual(u'Hello there\n', captured_output.stdout)
    self.assertEqual(0, self.ip.user_ns['_exit_code'])
    self.assertNotIn('_', self.ip.user_ns)

  def testGetOutputCompat(self):
    # "猫" is "cats" in simplified Chinese.
    captured_output = self.run_cell(
        '!!read res && echo "You typed: $res"', provided_inputs=[u'猫\n'])

    self.assertEqual('', captured_output.stderr)
    self.assertNotIn('_exit_code', self.ip.user_ns.keys())
    result = self.ip.user_ns['_']
    self.assertEqual(2, len(result))
    if six.PY2:
      self.assertEqual(u'猫'.encode('UTF-8'), result[0])
      self.assertEqual(u'You typed: 猫'.encode('UTF-8'), result[1])
    else:
      self.assertEqual(u'猫', result[0])
      self.assertEqual(u'You typed: 猫', result[1])

  def testGetOutputCompatWithInterrupt(self):
    captured_output = self.run_cell('!!read res', provided_inputs=['interrupt'])

    self.assertEqual('', captured_output.stderr)
    self.assertIn(u'^C\n', captured_output.stdout)
    result = self.ip.user_ns['_']
    self.assertEqual(0, len(result))

  def testGetOutputCompatWithVarExpansion(self):
    cmd = textwrap.dedent(u"""
      def some_func():
        local_var = 'Hello there'
        # The result of "!!" cannot be assigned or returned. Write the contents
        # to a file and return that instead.
        !!echo "{local_var}" > /tmp/getoutputwithvarexpansion.txt
        with open('/tmp/getoutputwithvarexpansion.txt', 'r') as f:
          print(f.read())
      some_func()
      """)
    captured_output = self.run_cell(cmd, provided_inputs=[])

    self.assertEqual('', captured_output.stderr)
    self.assertEqual(u'Hello there\n\n', captured_output.stdout)

  def run_cell(self, cell_contents, provided_inputs=None):
    """Execute the cell contents, optionally providing input to the subprocess.

    Args:
      cell_contents: Code to execute.
      provided_inputs: Input provided to the executing shell magic.

    Returns:
      Captured IPython output during execution.
    """
    result = self.run_cell_capture_update_calls(cell_contents, provided_inputs)
    return result.output

  def run_cell_capture_update_calls(self, cell_contents, provided_inputs=None):
    """Execute the cell contents, optionally providing input to the subprocess.

    Args:
      cell_contents: Code to execute.
      provided_inputs: Input provided to the executing shell magic.

    Returns:
      A RunCellWithUpdateCaptureResult containing the captured IPython output
      during execution and any calls to update echo status of the underlying
      shell.
    """

    # Why execute in a separate thread? The shell magic blocks until the
    # process completes, even if it is blocking on input. As such, we need to
    # asynchronously provide input by periodically popping the content and
    # forwarding it to the subprocess.
    def worker(inputs, result_container):

      def mock_stdin_provider():
        if not inputs:
          return None

        val = inputs.pop(0)
        if val == 'interrupt':
          raise KeyboardInterrupt
        return val

      mock_stdin_widget, echo_updater_calls = create_mock_stdin_widget()
      with \
        mock.patch.object(
            _message,
            '_read_stdin_message',
            side_effect=mock_stdin_provider,
            autospec=True), \
        mock.patch.object(
            _system_commands,
            '_display_stdin_widget',
            mock_stdin_widget):
        _system_commands._register_magics(self.ip)

        with io.capture_output() as captured:
          self.ip.run_cell(cell_contents)

        result_container.update({
            'output': captured,
            'echo_updater_calls': echo_updater_calls,
        })

    result = {}
    input_queue = []
    t = threading.Thread(
        target=worker, args=(
            input_queue,
            result,
        ))
    t.daemon = True
    t.start()

    provided_inputs = provided_inputs or []
    for provided_input in provided_inputs:
      time.sleep(2)
      input_queue.append(provided_input)

    t.join(30)
    self.assertFalse(t.is_alive())

    return RunCellWithUpdateCaptureResult(result['output'],
                                          result['echo_updater_calls'])


class DisplayStdinWidgetTest(unittest.TestCase):

  @mock.patch.object(_ipython, 'get_ipython', autospec=True)
  @mock.patch.object(_message, 'blocking_request', autospec=True)
  def testMessagesSent(self, mock_blocking_request, mock_get_ipython):
    mock_shell = mock.MagicMock(parent_header='12345')
    mock_get_ipython.return_value = mock_shell

    with _system_commands._display_stdin_widget(delay_millis=1000):
      pass

    mock_blocking_request.assert_has_calls([
        mock.call('cell_display_stdin', {'delayMillis': 1000}, parent='12345'),
        mock.call('cell_remove_stdin', {}, parent='12345'),
    ])


def create_mock_stdin_widget():
  calls = []

  @contextlib.contextmanager
  def mock_stdin_widget(*unused_args, **unused_kwargs):

    def echo_updater(echo):
      calls.append(echo)

    yield echo_updater

  return mock_stdin_widget, calls
