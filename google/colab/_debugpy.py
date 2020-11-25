"""Tools to enable debugpy attachment to a process."""

import threading

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

  _dap_port = portpicker.pick_unused_port()

  def attachment_entry():
    # The client will retry the connection a few times to avoid the inherent
    # raciness of this.
    debugpy.listen(_dap_port)

  # debugpy.listen will spin up another process then start listening for
  # connections from that process. This can take a second or so, but most of it
  # is not by this process. Doing this on a separate thread reduces the impact
  # on kernel initialization.
  threading.Thread(target=attachment_entry).start()

  return _dap_port
