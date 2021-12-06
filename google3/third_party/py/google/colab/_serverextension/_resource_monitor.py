"""Methods for tracking resource consumption of Colab kernels.

Note that this file is run under both py2 and py3 in tests.
"""

import csv
import os
import subprocess

from google.colab import _serverextension

try:
  # pylint: disable=g-import-not-at-top
  import psutil
except ImportError:
  psutil = None

# Track whether user has used the GPU in the current session.
_GPU_EVER_USED = False


def get_gpu_usage():
  """Reports total and per-kernel GPU memory usage.

  Returns:
    A dict of the form {
      usage: int,
      limit: int,
      ever_used : bool,
    }
  """
  global _GPU_EVER_USED

  usage = 0
  limit = 0
  try:
    ns = _serverextension._subprocess_check_output([  # pylint: disable=protected-access
        '/usr/bin/timeout', '-sKILL', '1s', 'nvidia-smi',
        '--query-gpu=memory.used,memory.total', '--format=csv,nounits,noheader'
    ]).decode('utf-8')
  except (OSError, IOError, subprocess.CalledProcessError):
    # If timeout or nvidia-smi don't exist or the call errors, return zero
    # values for usage and limit.
    pass
  else:
    r = csv.reader(ns.splitlines() or [''])
    row = next(r)
    usage = int(row[0]) * 1024 * 1024
    limit = int(row[1]) * 1024 * 1024

  if 'COLAB_FAKE_GPU_RESOURCES' in os.environ:
    usage, limit = 123, 456

  if usage:
    _GPU_EVER_USED = True

  return {'usage': usage, 'limit': limit, 'ever_used': _GPU_EVER_USED}


def get_ram_usage(kernel_manager):
  """Reports total and per-kernel RAM usage.

  Arguments:
    kernel_manager: an IPython MultiKernelManager that owns child kernel
      processes

  Returns:
    A dict of the form {
      usage: int,
      limit: int,
      kernels: A dict mapping kernel UUIDs to ints (memory usage in bytes),
    }
  """
  free, limit = 0, 0
  with open('/proc/meminfo', 'r') as f:
    lines = f.readlines()
  line = [x for x in lines if 'MemAvailable:' in x]
  if line:
    free = int(line[0].split()[1]) * 1024
  line = [x for x in lines if 'MemTotal:' in x]
  if line:
    limit = int(line[0].split()[1]) * 1024
  usage = limit - free
  result = {'usage': usage, 'limit': limit}
  if not os.path.exists('/var/colab/hostname'):
    pids_to_kernel_ids = dict([
        (str(kernel_manager.get_kernel(kernel_id).kernel.pid), kernel_id)
        for kernel_id in kernel_manager.list_kernel_ids()
    ])
    if pids_to_kernel_ids:
      kernels = {}
      ps = _serverextension._subprocess_check_output([  # pylint: disable=protected-access
          '/bin/ps', '-q', ','.join(pids_to_kernel_ids.keys()), '-wwo',
          'pid rss', '--no-header'
      ]).decode('utf-8')
      for proc in ps.split('\n')[:-1]:
        proc = proc.strip().split(' ', 1)
        if len(proc) != 2:
          continue
        kernels[pids_to_kernel_ids[proc[0]]] = int(proc[1]) * 1024
      result['kernels'] = kernels
  return result


def get_disk_usage(path=None):
  """Reports total disk usage.

  Args:
    path: path at which disk to be measured is mounted

  Returns:
    A dict of the form {
      usage: int,
      limit: int,
    }
  """
  if not path:
    path = '/'
  usage = 0
  limit = 0
  if psutil is not None:
    disk_usage = psutil.disk_usage(path)
    usage = disk_usage.used
    limit = disk_usage.total
  return {'usage': usage, 'limit': limit}
