"""API to add cells to the notebook."""

import google.colab._message as message


def create_scratch_cell(content, bottom_pane=False):
  """Opens a new scratch cell with the given contents.

  A popup will first be shown to the user to confirm that they trust the code
  being added.

  Args:
    content: The contents to add to the new scratch cell.
    bottom_pane: If True, add the scratch cell to the bottom pane instead of the
      right pane.

  Returns:
    None
  """
  message.blocking_request(
      'add_scratch_cell',
      request={'content': content, 'openInBottomPane': bottom_pane},
      timeout_sec=None,
  )
