"""Methods for tracking resource consumption of Colab kernels."""

import csv
import dataclasses
import functools
import os
import shutil
import subprocess

from google.colab import _serverextension
from google.colab import runtime

try:
  # pylint: disable=g-import-not-at-top
  import psutil
except ImportError:
  psutil = None

# Track whether user has used the GPU in the current session.
_GPU_EVER_USED = False

_T4_TOTAL_MEMORY_BYTES = 16106127360


@functools.cache
def _nvidia_smi_path():
  return shutil.which('nvidia-smi')


@dataclasses.dataclass
class GpuInfo:
  # Use camel case out of convenience as it allows us to use asdict() to
  # directly return the resource stats representation below.
  # pylint: disable=invalid-name
  name: str
  memoryUsedBytes: int
  memoryTotalBytes: int
  gpuUtilization: float
  memoryUtilization: float
  everUsed: bool
  # pylint: enable=invalid-name


def get_gpu_stats():
  """Reports stats for each GPU present in the system.

  Returns:
    A list of GpuInfo.
  """
  if 'COLAB_FAKE_GPU_RESOURCES' in os.environ:
    return [
        GpuInfo(
            name='Tesla T4',
            memoryUsedBytes=0.35 * _T4_TOTAL_MEMORY_BYTES,
            memoryTotalBytes=_T4_TOTAL_MEMORY_BYTES,
            gpuUtilization=0.1,
            memoryUtilization=0.35,
            everUsed=True,
        )
    ]

  nvidia_smi = _nvidia_smi_path()
  if not nvidia_smi:
    return []

  global _GPU_EVER_USED
  if 'COLAB_FAKE_GPU_RESOURCES' in os.environ:
    return [
        GpuInfo(
            name='Tesla T4',
            memoryUsedBytes=123,
            memoryTotalBytes=456,
            gpuUtilization=0.1,
            memoryUtilization=0.2,
            everUsed=True,
        )
    ]

  if not runtime._IS_EXTERNAL_COLAB:  # pylint: disable=protected-access
    return []

  usages = []
  try:
    ns = _serverextension._subprocess_check_output([  # pylint: disable=protected-access
        '/usr/bin/timeout',
        '-sKILL',
        '1s',
        nvidia_smi,
        # Note that the `nvidia-smi`'s sampling period of the utilization
        # metrics is sub-second. Sampling this function at a larger period may
        # miss periods of activity or inactivity.
        # The index is included to ensure a stable ordering in returned stats.
        '--query-gpu=index,name,memory.used,memory.total,utilization.gpu,utilization.memory',
        '--format=csv,nounits,noheader',
    ]).decode('utf-8')
  except (OSError, IOError, subprocess.CalledProcessError):
    # If timeout or nvidia-smi don't exist or the call errors, don't report on
    # any GPUs.
    # TODO: Add internal GPU memory monitoring. Install nvidia-smi.
    pass
  else:
    try:
      lines = ns.splitlines()
      lines.sort(key=lambda l: int(l.split(',', 1)[0]))
      for row in csv.reader(lines):
        memory_used = int(row[2]) * 1024 * 1024
        _GPU_EVER_USED |= memory_used > 0
        usages.append(
            GpuInfo(
                name=row[1].strip(),
                memoryUsedBytes=memory_used,
                memoryTotalBytes=int(row[3]) * 1024 * 1024,
                gpuUtilization=int(row[4]) / 100,
                memoryUtilization=int(row[5]) / 100,
                everUsed=memory_used > 0,
            )
        )
    except:  # pylint: disable=bare-except
      # Certain versions of nvidia-smi may not return the expected values. In
      # this case we don't report on any GPUs, even if we succeeded parsing for
      # some.
      usages = []

  return usages


def get_ram_usage(kernel_manager):
  """Reports total and per-kernel RAM usage.

  Arguments:
    kernel_manager: an IPython MultiKernelManager that owns child kernel
      processes.

  Returns:
    A dict of the form {
      usage: int,
      limit: int,
      kernels: A dict mapping kernel UUIDs to ints (memory usage in bytes),
    }
  """
  pids_to_kernel_ids = {}
  if not os.path.exists('/var/colab/hostname'):
    # TODO: Consider extending reporting per-kernel usage to
    # all environments for consistency. This was removed in cl/337174714. Its 1)
    # is better performed in the frontend presentation layer. 2) was only a
    # requirement for the split (KMC/K) container, a feature that was dropped
    # (cl/470476143).
    def get_pid(kernel):
      # TODO: Eliminate this function after migration to
      # jupyter-client 7.x is complete.
      try:
        pid = kernel.provisioner.pid
      except AttributeError:
        pid = kernel.kernel.pid
      return str(pid)

    pids_to_kernel_ids = {
        get_pid(kernel_manager.get_kernel(kernel_id)): kernel_id
        for kernel_id in kernel_manager.list_kernel_ids()
    }

  if 'TEST_TMPDIR' in os.environ:
    result = {'usage': 1 << 30, 'limit': 5 << 30}
    if pids_to_kernel_ids:
      per_kernel = result['usage'] // len(pids_to_kernel_ids)
      result['kernels'] = {k: per_kernel for k in pids_to_kernel_ids.values()}
    return result

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
  if pids_to_kernel_ids:
    kernels = {}
    ps = _serverextension._subprocess_check_output([  # pylint: disable=protected-access
        '/bin/ps',
        '-q',
        ','.join(pids_to_kernel_ids.keys()),
        '-wwo',
        'pid rss',
        '--no-header',
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
    path: path at which disk to be measured is mounted.

  Returns:
    A dict of the form {
      label: str,
      usage: int,
      limit: int,
    }
  """

  if not path:
    path = '/'

  if 'TEST_TMPDIR' in os.environ:
    if path == '/':
      return {'label': 'kernel', 'usage': 40 << 30, 'limit': 120 << 30}
    return {'label': path, 'usage': 80 << 30, 'limit': 240 << 30}

  usage = 0
  limit = 0
  label = 'kernel'

  if path != '/':
    label = path

  if psutil is not None:
    disk_usage = psutil.disk_usage(path)
    usage = disk_usage.used
    limit = disk_usage.total

  return {'label': label, 'usage': usage, 'limit': limit}


def get_resource_stats(kernel_manager, disk_paths=None):
  """Reports total disk usage.

  Why not return a proto message? Avoid a proto lib dep. It would add to our
  already complex dep management without much benefit.

  Args:
    kernel_manager: an IPython MultiKernelManager that owns child kernel
      processes.
    disk_paths: list of paths at which disks to be measured is mounted.

  Returns:
    A dict representation of a colab.resourcestats.Resources proto. I.e.:
      {
        'memory': {
          'totalBytes': 123,
          [...]
        }
        [...]
      }
  """
  ram = get_ram_usage(kernel_manager)
  if disk_paths is None:
    disk_paths = ['/']

  stats = {
      'memory': {
          'totalBytes': ram['limit'],
          'freeBytes': ram['limit'] - ram['usage'],
      },
      'disks': [_get_drive_stat(disk_path) for disk_path in disk_paths],
      'gpus': [dataclasses.asdict(gpu) for gpu in get_gpu_stats()],
  }

  if 'kernels' in ram:
    stats['memory']['kernels'] = [
        {'uuid': uuid, 'usedBytes': usage}
        for uuid, usage in ram['kernels'].items()
    ]

  return stats


def _get_drive_stat(disk_path=None):
  """Reports single disk usage.

  Args:
    disk_path: path at which disk to be measured is mounted.

  Returns:
    A dict representation of a colab.resourcestats.Disk.Filesystem proto.
    I.e.:
      {
        'filesystem': {
          'label': 'kernel',
          [...]
        }
        [...]
      }
  """

  disk = get_disk_usage(disk_path)
  return {
      'filesystem': {
          'label': disk['label'],
          'totalBytes': disk['limit'],
          'usedBytes': disk['usage'],
      }
  }
