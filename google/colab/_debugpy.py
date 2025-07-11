"""Tools to enable debugpy attachment to a process."""

import sys
from google.colab import _debugpy_repr
from google.colab import _variable_inspector

_dap_port = None


def enable_attach_async(enable_inspector=False):
  """Overrides python's breakpoint hook.

  Args:
    enable_inspector: Enable variable inspector.

  Returns:
      None
  """

  # debugpy overrides python's `breakpoint()` hook; we restore the original
  # hook, as it works fine with our stdin handling, and debugpy's hook hangs.
  sys.breakpointhook = sys.__breakpointhook__
