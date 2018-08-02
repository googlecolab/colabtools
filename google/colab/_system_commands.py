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
import subprocess
import sys
import termios

from IPython.core import magic
from IPython.core import magic_arguments
import six
from google.colab import _ipython
from google.colab import _message
from google.colab.output import _tags

# Linux read(2) limits to 0x7ffff000 so stay under that for clarity.
_PTY_READ_MAX_BYTES_FOR_TEST = 2**20  # 1MB

_ENCODING = 'UTF-8'


@magic.magics_class
class _ShellMagics(magic.Magics):
  """Magics for executing shell commands."""

  @magic.line_magic('shell')
  def _shell_line_magic(self, line):
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
    result = _run_command(line)
    result.check_returncode()
    return result

  @magic.cell_magic('shell')
  @magic_arguments.magic_arguments()
  @magic_arguments.argument(
      '--ignore-errors',
      dest='ignore_errors',
      action='store_true',
      help=('Don\'t raise a `subprocess.CalledProcessError` when the '
            'subprocess returns a non-0 exit code.'))
  def _shell_cell_magic(self, args, cmd):
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

    parsed_args = magic_arguments.parse_argstring(self._shell_cell_magic, args)

    result = _run_command(cmd)
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

  def _repr_pretty_(self, p, cycle):
    if cycle:
      raise NotImplementedError
    else:
      p.text(self.output)


def _configure_term_settings(pty_fd):
  term_settings = termios.tcgetattr(pty_fd)
  # ONLCR transforms NL to CR-NL, which is undesirable. Ensure this is disabled.
  # http://man7.org/linux/man-pages/man3/termios.3.html
  term_settings[1] &= ~termios.ONLCR

  # ECHOCTL echoes control characters, which is undesirable.
  term_settings[3] &= ~termios.ECHOCTL

  termios.tcsetattr(pty_fd, termios.TCSANOW, term_settings)


def _run_command(cmd):
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

  try:
    # Stdout / stderr writes by the subprocess are streamed to the cell's
    # output. Without this streaming, input could still be provided to the
    # process, but there would be no context as to what input was required.
    # Once the process has terminated, these outputs are no longer relevant and
    # should be cleared.
    # Note: When invoking the magic and not assigning the result
    # (e.g. %shell echo "foo"), Python's default semantics will be used and
    # print the string representation of the resultant ShellResult, which
    # is equivalent to the merged stdout/stderr outputs.
    with _tags.temporary(), display_stdin_widget(delay_millis=500):
      p = subprocess.Popen(
          cmd,
          shell=True,
          executable='/bin/bash',
          stdout=child_pty,
          stdin=child_pty,
          stderr=child_pty,
          close_fds=True)
      # The child PTY is only needed by the spawned process.
      os.close(child_pty)

      return _monitor_process(parent_pty, epoll, p, cmd)
  finally:
    epoll.close()
    os.close(parent_pty)


def _monitor_process(parent_pty, epoll, p, cmd):
  """Monitors the given subprocess until it terminates."""
  process_output = six.StringIO()

  is_pty_still_connected = True

  # A single UTF-8 character can span multiple bytes. os.read returns bytes and
  # could return a partial byte sequence for a UTF-8 character. Using an
  # incremental decoder is incrementally fed input bytes and emits UTF-8
  # characters.
  decoder = codecs.getincrementaldecoder(_ENCODING)()

  while True:
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
        sys.stdout.flush()
        process_output.write(decoded_contents)

      if event & select.EPOLLOUT:
        # Queue polling for inputs behind processing output events.
        input_events.append(event)

      # PTY was disconnected or encountered a connection error. In either case,
      # no new output should be made available.
      if (event & select.EPOLLHUP) or (event & select.EPOLLERR):
        is_pty_still_connected = False

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
    if terminated and not is_pty_still_connected and not output_available:
      command_output = process_output.getvalue()
      return ShellResult(cmd, p.returncode, command_output)


@contextlib.contextmanager
def display_stdin_widget(delay_millis=0):
  """Context manager that displays a stdin UI widget and hides it upon exit."""
  shell = _ipython.get_ipython()
  display_args = ['cell_display_stdin', {'delayMillis': delay_millis}]
  _message.send_request(*display_args, parent=shell.parent_header)

  yield

  hide_args = ['cell_remove_stdin', {}]
  _message.send_request(*hide_args, parent=shell.parent_header)
