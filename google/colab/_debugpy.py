"""Tools to enable debugpy attachment to a process."""

import debugpy
import portpicker

_dap_port = None


def enable_attach_async():
  """Enable a debugger to attach to this process.

  Returns:
    The debug adapter port which can be connected to using the Debug Adapter
    Proxy protocol.
  """
  global _dap_port
  if _dap_port:
    return _dap_port

  # TODO(b/64941125): Consider moving this earlier to avoid impact on kernel
  # connect time.
  _dap_port = portpicker.pick_unused_port()
  debugpy.listen(_dap_port)

  # TODO(b/175143091): Investigate what is causing the slowdowns here.
  debugpy.trace_this_thread(False)

  return _dap_port
