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

  # TODO(b/64941125): Consider moving this earlier to avoid impact on kernel
  # connect time.
  _dap_port = portpicker.pick_unused_port()

  main_thread = threading.current_thread()
  # Prevent debugpy from tracing the current thread.
  main_thread.pydev_do_not_trace = True

  def attachment_entry():
    # The client will retry the connection a few times to avoid the inherent
    # raciness of this.
    debugpy.listen(_dap_port)

    # Debugger tracing isn't needed for just tracebacks, but if full debugging
    # is needed then it needs to be re-enabled while debugging.
    # We want to use `pydevd.stoptrace` but if this is called before we have
    # connected to the debug adapter from the client then it'll send a
    # terminate to the adapter and the adapter will auto-exit before we can
    # connect to it. After the connection then it's OK to terminate since the
    # adapter will not close while there are active connections.
    threading.settrace(None)  # for all future threads
    try:
      # Stop debugpy from tracing newly created threads.
      from _pydev_bundle import pydev_monkey  # pylint: disable=g-import-not-at-top
      pydev_monkey.undo_patch_thread_modules()
    except ModuleNotFoundError:
      # _pydev_bundle may be vendored into either location.
      from debugpy.third_party.pydevd._pydev_bundle import pydev_monkey  # pylint: disable=g-import-not-at-top
      pydev_monkey.undo_patch_thread_modules()

    # Clear the trace flag to allow fetching stack traces.
    main_thread.pydev_do_not_trace = False

  # debugpy.listen will spin up another process then start listening for
  # connections from that process. This can take a second or so, but most of it
  # is not by this process. Doing this on a separate thread reduces the impact
  # on kernel initialization.
  threading.Thread(target=attachment_entry).start()

  return _dap_port
