"""Grid widget - allows to create a table, where each cell be printed into."""
import contextlib

from IPython import display
from google.colab.output import _publish

from google.colab.output import _util
from google.colab.widgets import _widget


class Grid(_widget.OutputAreaWidget):
  """Grid widget allows organizing outputs into NxM grid of individual cells.

  Each cell in this grid can be populated independently using standard
  ipython output functionality (such as print/display.HTML/matplotlib)

  Example:

  t = Grid(3, 4)
  with t.output_to(0, 0):
    print(1) # will print into cell (0, 0)

  t.clear_cell(0, 0)  # clears cell 0, 0

  with t.output_to(0, 1):
    print(1) # will print into cell (0, 1)

  with t.output_to(1,1):
    print(2)
    pylab.plot([1,2,3])

  etc...
  """

  def __init__(self,
               rows,
               columns,
               header_row=False,
               header_column=False,
               style=''):
    """Creates a new grid object.

    Args:
      rows: number of rows
      columns: number of columns
      header_row: if true will include header row (th)
      header_column: if true will include header column.
      style: a css string containing style for this grid.
    """
    self.rows = rows
    self.columns = columns
    self.header_row = header_row
    self.header_column = header_column
    self._id = _util.get_locally_unique_id()
    self._style = style
    super(Grid, self).__init__()

  def clear_cell(self, row=None, col=None):
    """Clears given cell. If row/col are None clears active cell."""
    if row is not None:
      if row < 0 or row >= self.rows:
        raise ValueError('%d is not a valid row' % row)
      if col < 0 or col >= self.columns:
        raise ValueError('%d is not a valid column' % col)
      cellid = self._get_cell_id(row, col)
    else:
      cellid = None
    self._clear_component(cellid)

  def _get_cell_id(self, row, col):
    return '%s-%s-%s' % (self._id, row, col)

  def __iter__(self):
    if not self._published:
      self._publish()
    for i in range(self.rows):
      for j in range(self.columns):
        with self.output_to(i, j):
          yield (i, j)

  def _populate(self, row_data, col_data, render, header_render=None):
    """Populate the grid with a cross product of row and cols."""

    def display_one_cell(render_func, *args):
      result = render_func(*args)
      if result is not None:
        display.display(result)

    header_render = header_render or display.display
    rows = list(row_data)
    cols = list(col_data)
    row_offset = 1 if self.header_row else 0
    col_offset = 1 if self.header_column else 0

    if (row_offset + len(rows) > self.rows or
        col_offset + len(cols) > self.columns):
      raise _widget.WidgetException('Can not fit %dx%d data into %dx%d grid. ' %
                                    (len(rows), len(cols), self.rows,
                                     self.columns))
    for row, col in iter(self):
      row -= row_offset
      col -= col_offset
      if row >= len(rows):
        continue
      if col >= len(cols):
        continue

      if row < 0 and col < 0:
        continue
      if row < 0:
        display_one_cell(header_render, cols[col])
        continue
      if col < 0:
        display_one_cell(header_render, rows[row])
        continue
      display_one_cell(render, rows[row], cols[col])
    return self

  def _html_repr(self):
    """Returns html representation of this grid."""
    html = '<table id=%s>' % (self._id,)

    for row in range(self.rows):
      html += '<tr>'
      for col in range(self.columns):
        if row == 0 and self.header_row or col == 0 and self.header_column:
          tag = 'th'
        else:
          tag = 'td'
        html += '<%(tag)s id=%(id)s></%(tag)s>' % {
            'tag': tag,
            'id': self._get_cell_id(row, col)
        }
      html += '</tr>'
    html += '</table>'
    return html

  def _publish(self):
    """Publishes the grid.

    Grid will publish automatically on first call to output_to.
    """

    if self._published:
      return
    super(Grid, self)._publish()
    with self._output_in_widget():
      _publish.css("""
       table#%(id)s, #%(id)s > tbody > tr > th, #%(id)s > tbody > tr > td {
         border: 1px solid lightgray;
         border-collapse:collapse;
         %(userstyle)s
        }""" % {
            'id': self._id,
            'userstyle': self._style
        })

      _publish.html(self._html_repr())

  @contextlib.contextmanager
  def output_to(self, row, column):
    """Redirects output to the corresponding cell of this grid.

    Args:
      row: 0 based row
      column: 0 based column

    Yields:
      nothing
    """
    if row < 0 or column < 0 or row >= self.rows or column >= self.columns:
      raise _widget.WidgetException(
          'Cell (%d, %d) is outside of boundaries of %dx%d grid' %
          (row, column, self.rows, self.columns))
    component_id = self._get_cell_id(row, column)
    with self._active_component(component_id):
      yield


def create_grid(row_data,
                col_data,
                render,
                header_render=None,
                header_row=True,
                header_column=True):
  """Creates Grid using cross product of rows and cols.


  This function populates the grid using row_data and col_data.
  In addition, if header_row/header_col are truthy it renders row[i] in 1st
  column and i-th row, as a header for row i, and, and col[i] in 1-st row
  and column j.

  Examples:

  Distance matrix between two vectors use
    create_grid(x, y, render=lambda x, y: np.linalg.norm(x-y))

  To render row-based data you can do:
    create_grid(data, range(10), render=lambda x, y: x[y]))

  For column based:
    create_grid(range(10), columns, render=lambda x, y: y[x]))

  Args:
    row_data: an iterable returning a generating element for each row
    col_data: an iterable returning a generating element for each col
    render: element display function. It should accept two arguments
    (corresponding row and column element).
    This function can produce output using either or both of two ways.
      1. It can use print statement, or any other display functions -
       such as pylab.show(), or display_html.
      2. It can return not None object to be rendered via IPython.display.
      This will produce repr(..) for vanilla python object and rich outputs
      for things like display.html.

    header_render: header display function that accepts one element to
    display. If no header rendering function is provided, each header
    is displayed using Python.display() function.
    header_row: if True the header row will be created
    header_column: if True the header column will be created.

  Raises:
    OutputWidgetException: if the grid size is not enough to
    render row/cols with their headers as requested.

  Returns:
    Filled grid for chaining.
  """
  rows = list(row_data)
  cols = list(col_data)
  t = Grid(
      len(rows) + header_row,
      len(cols) + header_column,
      header_row=header_row,
      header_column=header_column)
  # pylint: disable=protected-access
  t._populate(rows, cols, render, header_render)
  return t
