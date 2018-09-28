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
import socket
import sys
import uuid

import pexpect


def mount(mountpoint):
  """Mount your Google Drive at the specified mountpoint path."""

  mountpoint = os.path.expanduser(mountpoint)
  home = os.environ['HOME']
  root_dir = os.path.realpath(
      os.path.join(os.environ['CLOUDSDK_CONFIG'], '../..'))
  inet_family = 'IPV4_ONLY'
  dev = '/dev/fuse'
  path = '/usr/local/bin:/usr/local/sbin:/usr/bin:/usr/sbin:/bin:/sbin:.'
  if len(root_dir) > 1:
    home = os.path.join(root_dir, home)
    inet_family = 'IPV6_ONLY'
    fum = os.environ['HOME'].split('mount')[0] + '/mount/alloc/fusermount'
    dev = fum + '/dev/fuse'
    path = path + ':' + fum + '/bin'
  config_dir = os.path.join(home, '.config', 'Google')
  try:
    os.makedirs(config_dir)
  except OSError:
    if not os.path.isdir(config_dir):
      raise ValueError('{} must be a directory if present'.format(config_dir))

  # Launch an intermediate bash inside of which drive is launched, so that
  # after auth is done we can daemonize drive with its stdout/err no longer
  # being captured by pexpect. Otherwise buffers will eventually fill up and
  # drive may hang, because pexpect doesn't have a .startDiscardingOutput()
  # call (https://github.com/pexpect/pexpect/issues/54).
  prompt = u'root@{}-{}: '.format(socket.gethostname(), uuid.uuid4().hex)
  d = pexpect.spawn(
      '/bin/bash',
      args=['--noediting'],
      timeout=120,
      maxread=int(1e6),
      encoding='utf-8',
      env={
          'HOME': home,
          'FUSE_DEV_NAME': dev,
          'PATH': path
      })
  if mount._DEBUG:  # pylint:disable=protected-access
    d.logfile_read = sys.stdout
  d.sendline('export PS1="{}"'.format(prompt))
  d.expect(prompt)  # The echoed input above.
  d.expect(prompt)  # The new prompt.
  # Robustify to previously-running copies of drive. Don't only [pkill -9]
  # because that leaves enough cruft behind in the mount table that future
  # operations fail with "Transport endpoint is not connected".
  d.sendline('umount -f {mnt} || umount {mnt}; pkill -9 -x drive'.format(
      mnt=mountpoint))
  # Wait for above to be received, using the next prompt.
  d.expect(u'pkill')  # Echoed command.
  d.expect(prompt)
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
  d.expect(prompt)  # Eat the match of the input command above being echoed.
  drive_dir = os.path.join(root_dir, 'opt/google/drive')
  d.sendline(('{d}/drive --features=virtual_folders:true '
              '--inet_family=' + inet_family + ' '
              '--preferences=trusted_root_certs_file_path:'
              '{d}/roots.pem,mount_point_path:{mnt} --console_auth').format(
                  d=drive_dir, mnt=mountpoint))

  while True:
    case = d.expect(
        [success,
         prompt,
         re.compile(u'(Go to this URL in a browser: https://.*)\r\n')])
    if case == 0:
      break
    elif case == 1:
      # Prompt appearing here means something went wrong with the drive binary.
      d.terminate(force=True)
      raise ValueError('mount failed')
    elif case == 2:
      # Not already authorized, so do the authorization dance.
      prompt = d.match.group(1) + '\n\nEnter your authorization code:\n'
      d.send(getpass.getpass(prompt) + '\n')
  d.sendcontrol('z')
  d.expect(u'Stopped')
  d.sendline('bg; disown; exit')
  d.expect(pexpect.EOF)
  assert not d.isalive()
  assert d.exitstatus == 0
  print('Mounted at {}'.format(mountpoint))


mount._DEBUG = False  # pylint:disable=protected-access
