"""Methods for tracking resource consumption of Colab kernels.

Note that this file is run under both py2 and py3 in tox tests.
"""

import csv
import os
import subprocess

try:
  # pylint: disable=g-import-not-at-top
  import psutil
except ImportError:
  psutil = None


def get_gpu_usage():
  """Reports total and per-kernel GPU memory usage.

  Returns:
    A dict of the form {
      usage: int,
      limit: int,
      kernels: A dict mapping kernel UUIDs to ints (memory usage in bytes),
    }
  """
  gpu_memory_path = '/var/colab/gpu-memory'
  kernels = {}
  usage = 0
  limit = 0
  if os.path.exists(gpu_memory_path):
    with open(gpu_memory_path) as f:
      reader = csv.DictReader(f.readlines(), delimiter=' ')
      for row in reader:
        kernels[row['kernel_id']] = int(row['gpu_mem(MiB)']) * 1024 * 1024
  try:
    ns = subprocess.check_output([
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
  return {'usage': usage, 'limit': limit, 'kernels': kernels}


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
  pids_to_kernel_ids = dict([(str(
      kernel_manager.get_kernel(kernel_id).kernel.pid), kernel_id)
                             for kernel_id in kernel_manager.list_kernel_ids()])
  kernels = {}
  if pids_to_kernel_ids:
    ps = subprocess.check_output([
        'ps', '-q', ','.join(pids_to_kernel_ids.keys()), '-wwo', 'pid rss',
        '--no-header'
    ]).decode('utf-8')
    for proc in ps.split('\n')[:-1]:
      proc = proc.strip().split(' ', 1)
      if len(proc) != 2:
        continue
      kernels[pids_to_kernel_ids[proc[0]]] = int(proc[1]) * 1024
  return {'usage': usage, 'limit': limit, 'kernels': kernels}


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
