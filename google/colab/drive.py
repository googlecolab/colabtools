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
"""Colab-specific Google Drive integration."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import getpass
import os
import re
import sys

import pexpect


def mount(mountpoint):
  """Mount your Google Drive at the specified mountpoint path."""

  # Launch an intermediate bash inside of which drive is launched, so that
  # after auth is done we can daemonize drive with its stdout/err no longer
  # being captured by pexpect. Otherwise buffers will eventually fill up and
  # drive may hang, because pexpect doesn't have a .startDiscardingOutput()
  # call (https://github.com/pexpect/pexpect/issues/54).
  d = pexpect.spawn(
      '/bin/bash',
      timeout=120,
      maxread=int(1e6),
      encoding='utf-8',
      env={'HOME': os.environ['HOME']})
  # d.logfile_read = sys.stdout # Uncomment to ease debugging.
  # Robustify to previously-running copies of drive. Don't only [pkill -9]
  # because that leaves enough cruft behind in the mount table that future
  # operations fail with "Transport endpoint is not connected".
  d.sendline('umount -f {mnt}; pkill -9 drive'.format(mnt=mountpoint))
  d.expect(
      u'pkill.*# ')  # Wait for above to be received, using the next prompt.
  # Only check the mountpoint after potentially unmounting/pkill'ing above.
  try:
    if os.path.islink(mountpoint):
      raise ValueError('Mountpoint must not be a symlink')
    if os.path.isdir(mountpoint) and os.listdir(mountpoint):
      raise ValueError('Mountpoint must not already contain files')
    if not os.path.isdir(mountpoint) and os.path.exists(mountpoint):
      raise ValueError('Mountpoint must either be a directory or not exist')
  except:
    d.terminate(force=True)
    raise

  # Watch for success.
  success = u'google.colab.drive MOUNTED'
  success_watcher = (
      '( while `sleep 0.5`; do if [[ -d "{m}" && "$(ls -A {m})" != "" ]]; '
      'then echo "{s}"; break; fi; done ) &').format(
          m=mountpoint, s=success)
  d.sendline(success_watcher)
  d.expect(success)  # Eat the match of the input command above being echoed.
  d.sendline(('{d}/drive --features=virtual_folders:true '
              '--preferences=trusted_root_certs_file_path:'
              '{d}/roots.pem,mount_point_path:{mnt} --console_auth').format(
                  d='/opt/google/drive', mnt=mountpoint))
  i = d.expect(
      [success,
       re.compile(u'(Go to this URL in a browser: https://.*)\r\n')])
  if i:
    # Not already authorized, so do the authorization dance.
    print(d.match.group(1))
    sys.stdout.flush()
    d.expect(u'Enter your authorization code:')
    print(str(d.match.group(0)))
    sys.stdout.flush()
    d.send(getpass.getpass() + '\n')
    d.expect(success)  # Await success before returning to the user.
  d.sendcontrol('z')
  d.expect(u'Stopped')
  d.sendline('bg; disown; exit')
  d.expect(pexpect.EOF)
  assert not d.isalive()
  assert d.exitstatus == 0
  print('Mounted at {}'.format(mountpoint))
