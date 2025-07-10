"""Utility functions for fetching RAM usage."""

from google.colab import _serverextension


def get_total_ram() -> tuple[int, int]:
  """Returns the total RAM usage and limit."""
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
  return usage, limit


def get_per_kernel_ram_usage(kernel_manager) -> dict[str, int]:
  """Gets per-kernel RAM usage.

  Arguments:
    kernel_manager: an IPython MultiKernelManager that owns child kernel
      processes.

  Returns:
    A dict mapping kernel UUIDs to ints (memory usage in bytes)
  """

  def get_pid(kernel):
    # TODO: b/264409633 - Eliminate this function after migration to
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
  kernels = {}
  ps = _serverextension._subprocess_check_output([  # pylint: disable=protected-access
      '/bin/ps',
      '-q',
      ','.join(pids_to_kernel_ids.keys()),
      '-wwo',
      'pid rss',
      '--no-header',
  ]).decode(
      'utf-8'
  )
  for proc in ps.split('\n')[:-1]:
    proc = proc.strip().split(' ', 1)
    if len(proc) != 2:
      continue
    kernels[pids_to_kernel_ids[proc[0]]] = int(proc[1]) * 1024
  return kernels
