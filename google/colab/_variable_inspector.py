"""Variable inspector global inspection helper.

Since the module globals of the variable inspector thread are exposed as the
user namespace to the client (via debugpy) we effectively want to replace the
module globals with the user's globals from the user_ns. This module is
intentionally small to more easily avoid globals.
"""


def run(shell, time):
  """Spins updating globals from the user namespace.

  Args:
    shell: IPython shell object.
    time: Python time module.
  """

  # Clear all globals to avoid exposing them to the client and to ensure that
  # the following code can run with no globals.
  globals().clear()

  while True:
    time.sleep(.2)

    if shell:
      # Clear on each step to remove any deleted globals.
      # TODO(b/141957613): Validate that deleted variables disappear.
      globals().clear()
      globals().update(shell.user_ns)
