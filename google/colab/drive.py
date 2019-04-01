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

from __future__ import absolute_import as _
from __future__ import division as _
from __future__ import print_function as _

import collections as _collections
import getpass as _getpass
import os as _os
import re as _re
import socket as _socket
import subprocess as _subprocess
import sys as _sys
import uuid as _uuid

import pexpect as _pexpect

__all__ = ['mount']


_Environment = _collections.namedtuple(
    '_Environment',
    ('home', 'root_dir', 'inet_family', 'dev', 'path', 'config_dir'))


def _env():
  """Create and return an _Environment to use."""
  home = _os.environ['HOME']
  root_dir = _os.path.realpath(
      _os.path.join(_os.environ['CLOUDSDK_CONFIG'], '../..'))
  inet_family = 'IPV4_ONLY'
  dev = '/dev/fuse'
  path = '/usr/local/bin:/usr/local/sbin:/usr/bin:/usr/sbin:/bin:/sbin:.'
  if len(root_dir) > 1 and not root_dir.startswith('/usr/local/google/tmp/'):
    home = _os.path.join(root_dir, home)
    inet_family = 'IPV6_ONLY'
    fum = _os.environ['HOME'].split('mount')[0] + '/mount/alloc/fusermount'
    dev = fum + '/dev/fuse'
    path = path + ':' + fum + '/bin'
  config_dir = _os.path.join(home, '.config', 'Google')
  return _Environment(
      home=home,
      root_dir=root_dir,
      inet_family=inet_family,
      dev=dev,
      path=path,
      config_dir=config_dir)


def _timeouts_path():
  return _os.path.join(_env().config_dir, 'DriveFS/Logs/timeouts.txt')


def mount(mountpoint, force_remount=False, timeout_ms=15000):
  """Mount your Google Drive at the specified mountpoint path."""

  if ' ' in mountpoint:
    raise ValueError('Mountpoint must not contain a space.')

  mountpoint = _os.path.expanduser(mountpoint)
  # If we've already mounted drive at the specified mountpoint, exit now.
  already_mounted = _os.path.isdir(_os.path.join(mountpoint, 'My Drive'))
  if not force_remount and already_mounted:
    print('Drive already mounted at {}; to attempt to forcibly remount, '
          'call drive.mount("{}", force_remount=True).'.format(
              mountpoint, mountpoint))
    return

  env = _env()
  home = env.home
  root_dir = env.root_dir
  inet_family = env.inet_family
  dev = env.dev
  path = env.path
  config_dir = env.config_dir

  try:
    _os.makedirs(config_dir)
  except OSError:
    if not _os.path.isdir(config_dir):
      raise ValueError('{} must be a directory if present'.format(config_dir))

  # Launch an intermediate bash inside of which drive is launched, so that
  # after auth is done we can daemonize drive with its stdout/err no longer
  # being captured by pexpect. Otherwise buffers will eventually fill up and
  # drive may hang, because pexpect doesn't have a .startDiscardingOutput()
  # call (https://github.com/pexpect/pexpect/issues/54).
  prompt = u'root@{}-{}: '.format(_socket.gethostname(), _uuid.uuid4().hex)
  d = _pexpect.spawn(
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
    d.logfile_read = _sys.stdout
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
    if _os.path.islink(mountpoint):
      raise ValueError('Mountpoint must not be a symlink')
    if _os.path.isdir(mountpoint) and _os.listdir(mountpoint):
      raise ValueError('Mountpoint must not already contain files')
    if not _os.path.isdir(mountpoint) and _os.path.exists(mountpoint):
      raise ValueError('Mountpoint must either be a directory or not exist')
    normed = _os.path.normpath(mountpoint)
    if '/' in normed and not _os.path.exists(_os.path.dirname(normed)):
      raise ValueError('Mountpoint must be in a directory that exists')
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
  drive_dir = _os.path.join(root_dir, 'opt/google/drive')
  d.sendline(('{d}/drive '
              '--features=opendir_timeout_ms:{timeout_ms},virtual_folders:true '
              '--inet_family=' + inet_family + ' '
              '--preferences=trusted_root_certs_file_path:'
              '{d}/roots.pem,mount_point_path:{mnt} --console_auth').format(
                  d=drive_dir, timeout_ms=timeout_ms, mnt=mountpoint))

  # LINT.IfChange(drivetimedout)
  timeout_pattern = 'QueryManager timed out'
  # LINT.ThenChange()
  dfs_log = _os.path.join(config_dir, 'DriveFS/Logs/drive_fs.txt')

  while True:
    case = d.expect([
        success,
        prompt,
        _re.compile(u'(Go to this URL in a browser: https://.*)\r\n'),
        u'Drive File Stream encountered a problem and has stopped',
    ])
    if case == 0:
      break
    elif (case == 1 or case == 3):
      # Prompt appearing here means something went wrong with the drive binary.
      d.terminate(force=True)
      extra_reason = ''
      if 0 == _subprocess.call(
          'grep -q "{}" "{}"'.format(timeout_pattern, dfs_log), shell=True):
        extra_reason = (
            ': timeout during initial read of root folder; for more info: '
            'https://research.google.com/colaboratory/faq.html#drive-timeout')
      raise ValueError('mount failed' + extra_reason)
    elif case == 2:
      # Not already authorized, so do the authorization dance.
      auth_prompt = d.match.group(1) + '\n\nEnter your authorization code:\n'
      d.send(_getpass.getpass(auth_prompt) + '\n')
  d.sendcontrol('z')
  d.expect(u'Stopped')
  d.expect(prompt)
  d.sendline('bg; disown')
  d.expect(prompt)
  filtered_logfile = _timeouts_path()
  d.sendline('rm -rf "{}"'.format(filtered_logfile))
  d.expect(prompt)
  d.sendline(('tail -n +0 -F "{}" | '
              'grep --line-buffered "{}" > "{}" &'.format(
                  dfs_log, timeout_pattern, filtered_logfile)))
  d.expect(prompt)
  d.sendline('disown; exit')
  d.expect(_pexpect.EOF)
  assert not d.isalive()
  assert d.exitstatus == 0
  print('Mounted at {}'.format(mountpoint))


mount._DEBUG = False  # pylint:disable=protected-access
