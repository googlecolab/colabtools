"""Library for Interactive Table Widget in Colab."""

import importlib.resources
import anywidget
import traitlets


def _try_load_resource(fn: str) -> str:
  try:
    with importlib.resources.path("google.colab.widgets", fn) as resource:
      with open(resource) as f:
        return f.read()
  except FileNotFoundError:
    print(f"Warning: {fn!r} not found")
    return ""


class InteractiveTable(anywidget.AnyWidget):
  """An interactive table anywidget for Colab."""

  _css = _try_load_resource("_interactive_table.css")
  _esm = _try_load_resource("_interactive_table.js")

  # Python view of all the data
  data = None

  # Data sent by python and displayed by the frontend
  active_data = traitlets.List().tag(sync=True)
  columns = traitlets.List().tag(sync=True)
  rows = traitlets.Int(0).tag(sync=True)

  # Traits the frontend uses to update active_data
  page_num = traitlets.Int(0).tag(sync=True)
  page_size = traitlets.Int(10).tag(sync=True)
  sort_column = traitlets.Int(None, allow_none=True).tag(sync=True)
  sort_ascending = traitlets.Bool(True).tag(sync=True)

  def __init__(self, df=None, **kwargs):
    super().__init__(**kwargs)
    if df is not None:
      self.set_data(df)

  @traitlets.observe("page_num", "page_size", "sort_column", "sort_ascending")
  def _observe_state_change(self, _) -> None:
    self.update_active_data()

  def set_page(self, page_num: int):
    if page_num != self.page_num:
      self.page_num = page_num
      self.update_active_data()

  def update_active_data(self):
    if self.data is None:
      return

    start_row = self.page_num * self.page_size
    end_row = start_row + self.page_size

    if self.sort_column is not None:
      self.data.sort_values(
          by=self.columns[self.sort_column],
          ascending=self.sort_ascending,
          inplace=True,
      )

    # TODO: b/359279590 - not sure if I need to heal nan here.
    # Convert DataFrame to a list of records (dicts) for JSON serialization
    self.active_data = self.data[start_row:end_row].to_dict(orient="records")

  def set_data(self, df):
    self.data = df
    self.rows = len(self.data)
    self.columns = df.columns.tolist()
    self.page_num = 0
    self.update_active_data()
