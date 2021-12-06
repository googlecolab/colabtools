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
"""Colab-specific system command helpers."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import codecs
import contextlib
import locale
import os
import pty
import select
import signal
import subprocess
import sys
import termios
import time

from IPython.core import magic_arguments
from IPython.utils import text
import six
from google.colab import _ipython
from google.colab import _message
from google.colab.output import _tags

# Linux read(2) limits to 0x7ffff000 so stay under that for clarity.
_PTY_READ_MAX_BYTES_FOR_TEST = 2**20  # 1MB

_BIN_BASH = os.environ.get('BIN_BASH_OVERRIDE_FOR_TEST', '/bin/bash')
_ENCODING = 'UTF-8'


def _shell_line_magic(line):
  """Runs a shell command, allowing input to be provided.

  This is similar to Jupyter's `!` magic, but additionally allows input to be
  provided to the subprocess. If the subprocess returns a non-zero exit code
  a `subprocess.CalledProcessError` is raised. The provided command is run
  within a bash shell.

  Also available as a cell magic.

  Usage:
    # Returns a ShellResult.
    f = %shell echo "hello"

  Args:
    line: The shell command to execute.

  Returns:
    ShellResult containing the results of the executed command.

  Raises:
    subprocess.CalledProcessError: If the subprocess exited with a non-zero
      exit code.
  """
  result = _run_command(line, clear_streamed_output=False)
  result.check_returncode()
  return result


@magic_arguments.magic_arguments()
@magic_arguments.argument(
    '--ignore-errors',
    dest='ignore_errors',
    action='store_true',
    help=('Don\'t raise a `subprocess.CalledProcessError` when the '
          'subprocess returns a non-0 exit code.'))
def _shell_cell_magic(args, cmd):
  """Run the cell via a shell command, allowing input to be provided.

  Also available as a line magic.

  Usage:
    # Returns a ShellResult.
    %%shell
    echo "hello"

  This is similar to Jupyter's `!` magic, but additionally allows input to be
  provided to the subprocess. By default, if the subprocess returns a non-zero
  exit code a `subprocess.CalledProcessError` is raised. The provided command
  is run within a bash shell.

  Args:
    args: Optional arguments.
    cmd: The shell command to execute.

  Returns:
    ShellResult containing the results of the executed command.

  Raises:
    subprocess.CalledProcessError: If the subprocess exited with a non-zero
      exit code and the `ignore_errors` argument wasn't provided.
  """

  parsed_args = magic_arguments.parse_argstring(_shell_cell_magic, args)

  result = _run_command(cmd, clear_streamed_output=False)
  if not parsed_args.ignore_errors:
    result.check_returncode()
  return result


class ShellResult(object):
  """Result of an invocation of the shell magic.

  Note: This is intended to mimic subprocess.CompletedProcess, but has slightly
  different characteristics, including:
    * CompletedProcess has separate stdout/stderr properties. A ShellResult
      has a single property containing the merged stdout/stderr stream,
      providing compatibility with the existing "!" shell magic (which this is
      intended to provide an alternative to).
    * A custom __repr__ method that returns output. When the magic is invoked as
      the only statement in the cell, Python prints the string representation by
      default. The existing "!" shell magic also returns output.
  """

  def __init__(self, args, returncode, command_output):
    self.args = args
    self.returncode = returncode
    self.output = command_output

  def check_returncode(self):
    if self.returncode:
      raise subprocess.CalledProcessError(
          returncode=self.returncode, cmd=self.args, output=self.output)

  def _repr_pretty_(self, p, cycle):  # pylint:disable=unused-argument
    # Note: When invoking the magic and not assigning the result
    # (e.g. %shell echo "foo"), Python's default semantics will be used and
    # print the string representation of the object. By default, this will
    # display the __repr__ of ShellResult. Suppress this representation since
    # the output of the command has already been displayed to the output window.
    if cycle:
      raise NotImplementedError


def _configure_term_settings(pty_fd):
  term_settings = termios.tcgetattr(pty_fd)
  # ONLCR transforms NL to CR-NL, which is undesirable. Ensure this is disabled.
  # http://man7.org/linux/man-pages/man3/termios.3.html
  term_settings[1] &= ~termios.ONLCR

  # ECHOCTL echoes control characters, which is undesirable.
  term_settings[3] &= ~termios.ECHOCTL

  termios.tcsetattr(pty_fd, termios.TCSANOW, term_settings)


def _run_command(cmd, clear_streamed_output):
  """Calls the shell command, forwarding input received on the stdin_socket."""
  locale_encoding = locale.getpreferredencoding()
  if locale_encoding != _ENCODING:
    raise NotImplementedError(
        'A UTF-8 locale is required. Got {}'.format(locale_encoding))

  parent_pty, child_pty = pty.openpty()
  _configure_term_settings(child_pty)

  epoll = select.epoll()
  epoll.register(
      parent_pty,
      (select.EPOLLIN | select.EPOLLOUT | select.EPOLLHUP | select.EPOLLERR))

  stdin = child_pty
  if os.getenv('COLAB_DISABLE_STDIN_FOR_SHELL_MAGICS', None):
    stdin = os.open(os.devnull, os.O_RDWR)
  try:
    temporary_clearer = _tags.temporary if clear_streamed_output else _no_op

    with temporary_clearer(), _display_stdin_widget(
        delay_millis=500) as update_stdin_widget:
      # TODO(b/115531839): Ensure that subprocesses are terminated upon
      # interrupt.
      p = subprocess.Popen(
          cmd,
          shell=True,
          executable=_BIN_BASH,
          stdout=child_pty,
          stdin=stdin,
          stderr=child_pty,
          close_fds=True)
      # The child PTY is only needed by the spawned process.
      os.close(child_pty)

      return _monitor_process(parent_pty, epoll, p, cmd, update_stdin_widget)
  finally:
    epoll.close()
    os.close(parent_pty)


class _MonitorProcessState(object):

  def __init__(self):
    self.process_output = six.StringIO()
    self.is_pty_still_connected = True


def _monitor_process(parent_pty, epoll, p, cmd, update_stdin_widget):
  """Monitors the given subprocess until it terminates."""
  state = _MonitorProcessState()

  # A single UTF-8 character can span multiple bytes. os.read returns bytes and
  # could return a partial byte sequence for a UTF-8 character. Using an
  # incremental decoder is incrementally fed input bytes and emits UTF-8
  # characters.
  # In order to be consistent with IPython's treatment of non-UTF-8 output, make
  # use of the "replace" error handler within the decoder.
  # https://github.com/ipython/ipykernel/blob/master/ipykernel/iostream.py.
  decoder = codecs.getincrementaldecoder(_ENCODING)(errors='replace')

  num_interrupts = 0
  echo_status = None
  while True:
    try:
      result = _poll_process(parent_pty, epoll, p, cmd, decoder, state)
      if result is not None:
        return result

      term_settings = termios.tcgetattr(parent_pty)
      new_echo_status = bool(term_settings[3] & termios.ECHO)
      if echo_status != new_echo_status:
        update_stdin_widget(new_echo_status)
        echo_status = new_echo_status
    except KeyboardInterrupt:
      try:
        num_interrupts += 1
        if num_interrupts == 1:
          p.send_signal(signal.SIGINT)
        elif num_interrupts == 2:
          # Process isn't responding to SIGINT and user requested another
          # interrupt. Attempt to send SIGTERM followed by a SIGKILL if the
          # process doesn't respond.
          p.send_signal(signal.SIGTERM)
          time.sleep(0.5)
          if p.poll() is None:
            p.send_signal(signal.SIGKILL)
      except KeyboardInterrupt:
        # Any interrupts that occur during shutdown should not propagate.
        pass

      if num_interrupts > 2:
        # In practice, this shouldn't be possible since
        # SIGKILL is quite effective.
        raise


def _poll_process(parent_pty, epoll, p, cmd, decoder, state):
  """Polls the process and captures / forwards input and output."""

  terminated = p.poll() is not None
  if terminated:
    termios.tcdrain(parent_pty)
    # We're no longer interested in write events and only want to consume any
    # remaining output from the terminated process. Continuing to watch write
    # events may cause early termination of the loop if no output was
    # available but the pty was ready for writing.
    epoll.modify(parent_pty,
                 (select.EPOLLIN | select.EPOLLHUP | select.EPOLLERR))

  output_available = False

  events = epoll.poll()
  input_events = []
  for _, event in events:
    if event & select.EPOLLIN:
      output_available = True
      raw_contents = os.read(parent_pty, _PTY_READ_MAX_BYTES_FOR_TEST)
      decoded_contents = decoder.decode(raw_contents)

      sys.stdout.write(decoded_contents)
      state.process_output.write(decoded_contents)

    if event & select.EPOLLOUT:
      # Queue polling for inputs behind processing output events.
      input_events.append(event)

    # PTY was disconnected or encountered a connection error. In either case,
    # no new output should be made available.
    if (event & select.EPOLLHUP) or (event & select.EPOLLERR):
      state.is_pty_still_connected = False

  for event in input_events:
    # Check to see if there is any input on the stdin socket.
    # pylint: disable=protected-access
    input_line = _message._read_stdin_message()
    # pylint: enable=protected-access
    if input_line is not None:
      # If a very large input or sequence of inputs is available, it's
      # possible that the PTY buffer could be filled and this write call
      # would block. To work around this, non-blocking writes and keeping
      # a list of to-be-written inputs could be used. Empirically, the
      # buffer limit is ~12K, which shouldn't be a problem in most
      # scenarios. As such, optimizing for simplicity.
      input_bytes = bytes(input_line.encode(_ENCODING))
      os.write(parent_pty, input_bytes)

  # Once the process is terminated, there still may be output to be read from
  # the PTY. Wait until the PTY has been disconnected and no more data is
  # available for read. Simply waiting for disconnect may be insufficient if
  # there is more data made available on the PTY than we consume in a single
  # read call.
  if terminated and not state.is_pty_still_connected and not output_available:
    sys.stdout.flush()
    command_output = state.process_output.getvalue()
    return ShellResult(cmd, p.returncode, command_output)

  if not output_available:
    # The PTY is almost continuously available for reading input to provide
    # to the underlying subprocess. This means that the polling loop could
    # effectively become a tight loop and use a large amount of CPU. Add a
    # slight delay to give resources back to the system while monitoring the
    # process.
    # Skip this delay if we read output in the previous loop so that a partial
    # read doesn't unnecessarily sleep before reading more output.
    # TODO(b/115527726): Rather than sleep, poll for incoming messages from
    # the frontend in the same poll as for the output.
    time.sleep(0.1)


@contextlib.contextmanager
def _display_stdin_widget(delay_millis=0):
  """Context manager that displays a stdin UI widget and hides it upon exit.

  Args:
    delay_millis: Duration (in milliseconds) to delay showing the widget within
      the UI.

  Yields:
    A callback that can be invoked with a single argument indicating whether
    echo is enabled.
  """
  shell = _ipython.get_ipython()
  display_args = ['cell_display_stdin', {'delayMillis': delay_millis}]
  _message.send_request(
      *display_args, parent=shell.parent_header, expect_reply=False)

  def echo_updater(new_echo_status):
    # Note: Updating the echo status uses colab_request / colab_reply on the
    # stdin socket. Input provided by the user also sends messages on this
    # socket. If user input is provided while the blocking_request call is still
    # waiting for a colab_reply, the input will be dropped per
    # https://github.com/googlecolab/colabtools/blob/56e4dbec7c4fa09fad51b60feb5c786c69d688c6/google/colab/_message.py#L100.
    update_args = ['cell_update_stdin', {'echo': new_echo_status}]
    _message.send_request(
        *update_args, parent=shell.parent_header, expect_reply=False)

  yield echo_updater

  _message.send_request(
      'cell_remove_stdin', {}, parent=shell.parent_header, expect_reply=False)


@contextlib.contextmanager
def _no_op():
  yield


def _register_magics(ip):
  ip.register_magic_function(
      _shell_line_magic, magic_kind='line', magic_name='shell')
  ip.register_magic_function(
      _shell_cell_magic, magic_kind='cell', magic_name='shell')


_INTERRUPTED_SIGNALS = (
    signal.SIGINT,
    signal.SIGTERM,
    signal.SIGKILL,
)


def _getoutput_compat(shell, cmd, split=True, depth=0):
  """Compatibility function for IPython's built-in getoutput command.

  The getoutput command has the following semantics:
    * Returns a SList containing an array of output
    * SList items are of type "str". In Python 2, the str object is utf-8
      encoded. In Python 3, the "str" type already supports Unicode.
    * The _exit_code attribute is not set
    * If the process was interrupted, "^C" is printed.

  Args:
    shell: An InteractiveShell instance.
    cmd: Command to execute. This is the same as the corresponding argument to
      InteractiveShell.getoutput.
    split: Same as the corresponding argument to InteractiveShell.getoutput.
    depth: Same as the corresponding argument to InteractiveShell.getoutput.
  Returns:
    The output as a SList if split was true, otherwise an LSString.
  """
  # We set a higher depth than the IPython system command since a shell object
  # is expected to call this function, thus adding one level of nesting to the
  # stack.
  result = _run_command(
      shell.var_expand(cmd, depth=depth + 2), clear_streamed_output=True)
  if -result.returncode in _INTERRUPTED_SIGNALS:
    print('^C')

  output = result.output
  if six.PY2:
    # Backwards compatibility. Python 2 getoutput() expects the result as a
    # str, not a unicode.
    output = output.encode(_ENCODING)

  if split:
    return text.SList(output.splitlines())
  else:
    return text.LSString(output)


def _system_compat(shell, cmd, also_return_output=False):
  """Compatibility function for IPython's built-in system command.

  The system command has the following semantics:
    * No return value, and thus the "_" variable is not set
    * Sets the _exit_code variable to the return value of the called process
    * Unicode characters are preserved
    * If the process was interrupted, "^C" is printed.

  Args:
    shell: An InteractiveShell instance.
    cmd: Command to execute. This is the same as the corresponding argument to
      InteractiveShell.system_piped.
    also_return_output: if True, return any output from this function, along
      with printing it. Otherwise, print output and return None.
  Returns:
    LSString if also_return_output=True, else None.
  """
  # We set a higher depth than the IPython system command since a shell object
  # is expected to call this function, thus adding one level of nesting to the
  # stack.
  result = _run_command(
      shell.var_expand(cmd, depth=2), clear_streamed_output=False)
  shell.user_ns['_exit_code'] = result.returncode
  if -result.returncode in _INTERRUPTED_SIGNALS:
    print('^C')

  if also_return_output:
    output = result.output
    if six.PY2:
      # Backwards compatibility. Python 2 getoutput() expects the result as a
      # str, not a unicode.
      output = output.encode(_ENCODING)
    return text.LSString(output)
