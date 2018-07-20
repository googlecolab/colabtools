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
from google.colab import _message
from google.colab.output import _tags

_PTY_READ_MAX_BYTES_FOR_TEST = 1024

_ENCODING = 'UTF-8'


@magic.magics_class
class _ShellMagics(magic.Magics):
  """Magics for executing shell commands."""

  def __init__(self, shell, **call_process_kwargs):
    super(_ShellMagics, self).__init__(shell)
    self._call_process_kwargs = call_process_kwargs or {}

  @magic.line_magic('shell')
  def _shell_line_magic(self, line):
    """Runs a shell command, allowing input to be provided.

    This is similar to Jupyter's `!` magic, but additionally allows input to be
    provided to the subprocess. If the subprocess returns a non-zero exit code
    a `subprocess.CalledProcessError` is raised.

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
    result = _run_command(line, **self._call_process_kwargs)
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
    exit code a `subprocess.CalledProcessError` is raised.

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

    result = _run_command(cmd, **self._call_process_kwargs)
    if not parsed_args.ignore_errors:
      result.check_returncode()
    return result


class ShellResult(object):
  """Result of an invocation of the shell magic.

  Note: This is intended to mimic subprocess.CompletedProcess, but has slightly
  different characteristics, including:
    * ProcessResult has separate stdout/stderr. The existing "!" shell magic
      (which this is intended to provide an alternative to) returns unseparated
      stdout/stderr output that would be difficult to reconstruct from separate
      streams.
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

  def __repr__(self):
    return self.output


def _configure_pty_settings(pty_fd):
  term_settings = termios.tcgetattr(pty_fd)
  # ONLCR transforms NL to CR-NL, which is undesirable. Ensure this is disabled.
  # http://man7.org/linux/man-pages/man3/termios.3.html
  term_settings[1] &= ~termios.ONLCR

  # ECHOCTL echoes control characters, which is undesirable.
  term_settings[3] &= ~termios.ECHOCTL

  termios.tcsetattr(pty_fd, termios.TCSANOW, term_settings)


def _run_command(cmd, read_stdin_message=None):
  """Calls the shell command, forwarding input received on the stdin_socket."""
  locale_encoding = locale.getpreferredencoding()
  if locale_encoding != _ENCODING:
    raise NotImplementedError(
        'A UTF-8 locale is required. Got {}'.format(locale_encoding))

  # TODO(b/36984411): Create a UI widget to capture stdin and forward an
  # input_reply to the kernel.
  # pylint: disable=protected-access
  read_stdin_message = read_stdin_message or _message._read_stdin_message
  # pylint: enable=protected-access

  parent_pty, child_pty = pty.openpty()
  _configure_pty_settings(child_pty)

  # TODO(b/36984411): Having a separate PTY for stderr adds a bit of complexity.
  # Consider merging stdout/stderr.
  stderr_parent_pty, stderr_child_pty = pty.openpty()
  _configure_pty_settings(stderr_child_pty)

  epoll = select.epoll()
  epoll.register(
      parent_pty,
      (select.EPOLLIN | select.EPOLLOUT | select.EPOLLHUP | select.EPOLLERR))
  epoll.register(stderr_parent_pty,
                 (select.EPOLLIN | select.EPOLLHUP | select.EPOLLERR))

  pty_to_stream = {
      parent_pty: sys.stdout,
      stderr_parent_pty: sys.stderr,
  }

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
    with _tags.temporary():
      p = subprocess.Popen(
          # TODO(b/36984411): Consider always running the command within a bash
          # subshell.
          cmd,
          shell=True,
          stdout=child_pty,
          stdin=child_pty,
          stderr=stderr_child_pty,
          close_fds=True)
      # child PTYs are only needed by the spawned process.
      os.close(child_pty)
      os.close(stderr_child_pty)

      return _monitor_process(pty_to_stream, epoll, p, cmd, read_stdin_message)
  finally:
    epoll.close()
    for parent_pty in pty_to_stream:
      os.close(parent_pty)


def _monitor_process(pty_to_stream, epoll, p, cmd, read_stdin_message):
  """Monitors the given subprocess until it terminates."""
  process_output = six.StringIO()

  connected_ptys = set(pty_to_stream.keys())

  # A single UTF-8 character can span multiple bytes. os.read returns bytes and
  # could return a partial byte sequence for a UTF-8 character. Using an
  # incremental decoder is incrementally fed input bytes and emits UTF-8
  # characters.
  pty_to_decoder = {
      pty_fd: codecs.getincrementaldecoder(_ENCODING)()
      for pty_fd, _ in pty_to_stream.items()
  }

  while True:
    terminated = p.poll() is not None
    if terminated:
      for stream_pty in pty_to_stream:
        termios.tcdrain(stream_pty)
        # We're no longer interested in write events and only want to consume
        # any remaining output from the terminated process. Continuing to watch
        # write events may cause early termination of the loop if no output was
        # available but the pty was ready for writing.
        epoll.modify(stream_pty,
                     (select.EPOLLIN | select.EPOLLHUP | select.EPOLLERR))

    output_available = False

    events = epoll.poll()
    input_events = []
    for fd, event in events:
      if event & select.EPOLLIN:
        output_available = True
        # TODO(b/36984411): Convert the PTY to allow non-blocking reads. Then,
        # anytime a readable event occurs, continue reading the PTY until
        # drained so that all available input is flushed.
        raw_contents = os.read(fd, _PTY_READ_MAX_BYTES_FOR_TEST)
        decoded_contents = pty_to_decoder[fd].decode(raw_contents)

        stream = pty_to_stream[fd]
        stream.write(decoded_contents)
        stream.flush()
        process_output.write(decoded_contents)

      if event & select.EPOLLOUT:
        # Queue polling for inputs behind processing output events.
        input_events.append((fd, event))

      # PTY was disconnected or encountered a connection error. In either case,
      # no new output should be made available.
      if (event & select.EPOLLHUP) or (event & select.EPOLLERR):
        connected_ptys.discard(fd)

    for fd, event in input_events:
      # Check to see if there is any input on the stdin socket.
      input_line = read_stdin_message()
      if input_line is not None:
        # If a very large input or sequence of inputs is available, it's
        # possible that the PTY buffer could be filled and this write call
        # would block. To work around this, non-blocking writes and keeping
        # a list of to-be-written inputs could be used. Empirically, the
        # buffer limit is ~12K, which shouldn't be a problem in most
        # scenarios. As such, optimizing for simplicity.
        input_bytes = bytes(input_line.encode(_ENCODING))
        os.write(fd, input_bytes)

    # Once the process is terminated, there still may be output to be read from
    # the PTYs. Wait until PTYs have been disconnected and no more data is
    # available for read. Simply waiting for disconnect may be insufficient if
    # there is more data made available on the PTY than we consume in a single
    # read call.
    if terminated and not connected_ptys and not output_available:
      command_output = process_output.getvalue()
      return ShellResult(cmd, p.returncode, command_output)
