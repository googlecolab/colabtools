"""Methods for tracking resource consumption of Colab kernels."""
import csv
import os
import re
import subprocess
from distutils import spawn

_cmd_regex = re.compile(r'.+kernel-(.+)\.json.*')


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
  if spawn.find_executable('nvidia-smi') is not None:
    ns = subprocess.check_output([
        'nvidia-smi', '--query-gpu=memory.used,memory.total',
        '--format=csv,nounits,noheader'
    ]).decode('utf-8')
    r = csv.reader([ns])
    row = next(r)
    usage = int(row[0]) * 1024 * 1024
    limit = int(row[1]) * 1024 * 1024
  return {'usage': usage, 'limit': limit, 'kernels': kernels}


def get_ram_usage():
  """Reports total and per-kernel RAM usage.

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
  kernels = {}
  ps = subprocess.check_output(
      ['ps', '--ppid',
       str(os.getpid()), '-wwo', 'rss cmd', '--no-header']).decode('utf-8')
  for proc in ps.split('\n')[:-1]:
    proc = proc.strip().split(' ', 1)
    if len(proc) != 2:
      continue
    if not re.match(_cmd_regex, proc[1]):
      continue
    kernel_id = re.sub(_cmd_regex, r'\1', proc[1])
    kernels[kernel_id] = int(proc[0]) * 1024
  return {'usage': usage, 'limit': limit, 'kernels': kernels}
