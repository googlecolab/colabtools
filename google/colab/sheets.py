"""Helper class to build interactive sheets."""

import abc
import datetime
import importlib
import operator
import google.auth
from google.colab import auth
import gspread
from gspread import utils as gspread_utils
import IPython
import numpy as np
import pandas as pd

_gspread_client = None


_PANDAS = 'pandas'
_POLARS = 'polars'


def _clean_val(val):
  if isinstance(val, pd.Timestamp):
    return val.isoformat()
  if isinstance(val, np.longdouble):
    return float(val)
  if isinstance(val, list):
    return str(val)
  return val


def _to_frame(index):
  if isinstance(index, pd.MultiIndex):
    frame = index.to_frame(index=False)
  else:
    # workaround for https://github.com/pandas-dev/pandas/issues/25809
    frame = pd.DataFrame(index)
  return frame.map(_clean_val).replace({np.nan: None})


def _generate_creds(unused_credentials=None):
  auth.authenticate_user()
  scopes = (
      'https://www.googleapis.com/auth/drive',
      'https://www.googleapis.com/auth/spreadsheets',
  )
  creds, _ = google.auth.default(scopes=scopes)
  return creds


def _standardize_location(loc: str | tuple[int, int]) -> str:
  """Returns the location standardized to "A1" format.

  Args:
    loc: The location either in A1 notation (e.g. A1, C8 or DA3) or as 1-based
      (row, column) tuples (e.g. (1, 1), (8, 3) or (3, 105)).

  Returns:
    The location standardized to A1 format if it wasn't already in that format.
  """
  match loc:
    case '':
      return loc
    case str() if gspread_utils.CELL_ADDR_RE.match(loc) is not None:
      return loc
    case (row, col) if row > 0 and col > 0:
      return gspread_utils.rowcol_to_a1(row, col)
    case _:
      raise ValueError(
          f'{loc} is not a valid location, provide either A1 notation or a'
          ' 1-based (row, column) tuple.'
      )


class InteractiveSheet:
  """A lightweight wrapper to embed interactive sheets in Colab iframes.

  Public methods:
    as_df: fetches the data in the current worksheet and returns a new dataframe
    update: clears the sheet and replaces it with the provided dataframe
    display: displays the embedded sheet in Colab

  Attributes:
    sheet: a gspread.models.Spreadsheet that contains the worksheet
    worksheet: a gspread.models.Worksheet that contains the data for this
      InteractiveSheet
    url: a string with the url to the sheet
    embedded_url: a string with the url to the embedded sheet
    storage_strategy: an instance of InteractiveSheetStorageStrategy
    backend: A string indicating the backend the interactive sheet uses
  """

  def __init__(
      self,
      *,
      title='',
      url='',
      sheet_id='',
      df=None,
      worksheet_id=None,
      worksheet_name='',
      credentials=None,
      include_column_headers=True,
      display=True,
      backend=_PANDAS,
  ):
    """Initialize a new InteractiveSheet.

    Notes:
      - if url, sheet_id and title are empty a new sheet will be created.
      - only one of title, url, or sheet_id can be provided to load a sheet
      - only one of worksheet_id OR worksheet_name can be provided

    Args:
      title: If provided, load data from the worksheet with this title
      url: If provided, use this sheets URL to source the data
      sheet_id: If provided, use this sheet id to source the data. Note -
        sheet_id is the Drive ID from the sheets URL, i.e.
        https://docs.google.com/spreadsheets/d/{sheet_id}/edit.
      df: If provided, populate the sheet with this data
      worksheet_id: If provided, load data from this worksheet_id. Note -
        worksheet_id indicates which worksheet (tab) to use. Worksheet_id is the
        optional query param, `gid` in the sheets URL i.e.
        https://docs.google.com/spreadsheets/d/{sheet_id}/edit?gid={worksheet_id}.
      worksheet_name: If provided, load data from this worksheet_name
      credentials: If provided, use these oauth credentials.
      include_column_headers: If True, assume the first row of the sheet is a
        header column for both reads and writes.
      display: If True, displays the embedded sheet in the cell output.
      backend: The dataframe lbrary to use, must be one of `'pandas'` or
        `'polars'`. To use polars it must actually be installed.

    Raises:
      ValueError: When an incompatible `backend` is supplied.
      ModuleNotFoundError: When `backend='polars'` but polars is not installed.
    """
    if sum([bool(url), bool(sheet_id), bool(title)]) > 1:
      raise ValueError(
          'Expected either a `url`, `sheet_id` or `title` but got more than'
          ' one.'
      )

    if worksheet_id is not None and worksheet_name:
      raise ValueError('Expected `worksheet_id` or `worksheet_name` got both.')

    if sheet_id:
      url = f'https://docs.google.com/spreadsheets/d/{sheet_id}'
    self._credentials = credentials
    self._ensure_gspread_client()

    self.sheet = self._load_or_create_sheet(url, title)

    if worksheet_name:
      self.worksheet = self.sheet.worksheet(worksheet_name)
    elif worksheet_id is not None:
      self.worksheet = self.sheet.get_worksheet_by_id(worksheet_id)
    else:
      # Default to the first worksheet.
      self.worksheet = self.sheet.get_worksheet(0)

    self.url = f'{self.sheet.url}/edit#gid={self.worksheet.id}'
    # Printing the URL gives the user a convenient handle to the pointer page.
    print(self.url)
    self.embedded_url = (
        f'{self.sheet.url}/edit?rm=embedded#gid={self.worksheet.id}'
    )
    self.backend = backend
    if backend == _POLARS:
      self.storage_strategy = (
          PolarsHeaderStorageStrategy()
          if include_column_headers
          else PolarsHeaderlessStorageStrategy()
      )
    elif backend == _PANDAS:
      self.storage_strategy = (
          HeaderStorageStrategy()
          if include_column_headers
          else HeaderlessStorageStrategy()
      )
    else:
      raise ValueError(
          f"Unrecognized backend '{backend}', use one of 'polars' or 'pandas'."
      )
    if df is not None:
      self.update(df=df)
    if display:
      self.display()

  def _load_or_create_sheet(self, url='', title=''):
    """A helper function to load a sheet.

    If neither url or title argument is provided a new sheet will be created.

    Args:
      url: if provided, source data from this sheets url
      title: if provided, search the users sheets for this title, else make a
        new sheet with this titles

    Returns:
      a gspread sheet
    """
    if url:
      return _gspread_client.open_by_url(url)
    if title:
      try:
        return _gspread_client.open(title)
      except gspread.exceptions.SpreadsheetNotFound:
        return _gspread_client.create(title)

    title = datetime.datetime.now().strftime(
        'InteractiveSheet_%Y-%m-%d_%H_%M_%S'
    )

    return _gspread_client.create(title)

  def _ensure_gspread_client(self):
    global _gspread_client
    if _gspread_client is None:
      creds = InteractiveSheet.generate_creds(self._credentials)
      _gspread_client = gspread.authorize(creds)

  @classmethod
  def generate_creds(cls, credentials=None):
    return _generate_creds(credentials)

  def as_df(self, range_name=None):
    """as_df fetches the data in the current worksheet and returns a new dataframe.

    Args:
      range_name: the range of data to fetch, defaults to the entire worksheet

    Returns:
      a pandas Dataframe with the latest data from the current worksheet
    """
    self._ensure_gspread_client()
    return self.storage_strategy.read(self.worksheet, range_name)

  def update(self, df, location='', clear=True, **kwargs):
    """Update clears the sheet and replaces it with the provided dataframe.

    Args:
      df: the source data
      location: The top left most cell in the worksheet to write data in. Can be
        provided either in A1 notation or as a 1-based (row, column) tuple. An
        empty string defaults to A1.
      clear: Whether to clear other content before writing data to the sheet.
        This is useful when you want to update a worksheet with a dataframe that
        may have fewer rows than before but needs to be disabled when you are
        writing successive dataframes in other locations to keep previously
        written data.
      **kwargs: additional arguments to pass to the gspread update method

    Raises:
      ValueError: When a pandas dataframe is passed to an instance with
      `backend='polars'` or vice versa.
    """
    if df is None:
      raise ValueError('df must be a non-empty dataframe')

    if self.backend == _POLARS and isinstance(df, pd.DataFrame):
      raise ValueError(
          'Unexpected DataFrame. Got: pandas, want: polars. To use a pandas'
          " dataframe with InteractiveSheet you must set backend='pandas' when"
          ' creating the sheet'
      )
    if self.backend == _PANDAS and not isinstance(df, pd.DataFrame):
      raise ValueError(
          'Unexpected DataFrame. Got: polars, want: pandas. To use a polars'
          " dataframe with InteractiveSheet you must set backend='polars' when"
          ' creating the sheet'
      )
    self._ensure_gspread_client()
    if clear:
      self.worksheet.clear()
    frame = df if (self.backend == _POLARS) else _to_frame(df)
    self.storage_strategy.write(
        self.worksheet, frame, _standardize_location(location), **kwargs
    )

  def display(self, height=600):
    """Display the embedded sheet in Colab.

    Args:
      height: the height in pixels for the displayed sheet
    """
    IPython.display.display(
        IPython.display.IFrame(self.embedded_url, height=height, width='100%')
    )


class InteractiveSheetStorageStrategy(abc.ABC):
  """Declares read and write operations for an InteractiveSheet."""

  @abc.abstractmethod
  def read(self, worksheet):
    pass

  @abc.abstractmethod
  def write(self, worksheet, df, location, **kwargs):
    pass


class HeaderlessStorageStrategy(InteractiveSheetStorageStrategy):
  """Read and write operations for sheets with a header row."""

  def read(self, worksheet, range_name=None):
    data = worksheet.get_values(range_name)
    return pd.DataFrame(data)

  def write(self, worksheet, df, location, **kwargs):
    data = [list(r) for _, r in df.iterrows()]
    worksheet.update(location, data, **kwargs)


class HeaderStorageStrategy(InteractiveSheetStorageStrategy):
  """Read and write operations for sheets without a header row."""

  def read(self, worksheet, range_name=None):
    data = worksheet.get_values(range_name)
    if not data:
      return pd.DataFrame()
    # Data is a list of lists, i.e.
    # [[header1, header2], [row1col1, row1col2], ...], where the first element
    # is the column names, the rest are the rows.
    columns = data[0]
    rows = data[1:]
    return pd.DataFrame(rows, columns=columns)

  def write(self, worksheet, df, location, **kwargs):
    data = [list(df.columns)] + [list(r) for _, r in df.iterrows()]
    worksheet.update(location, data, **kwargs)


class PolarsHeaderlessStorageStrategy(InteractiveSheetStorageStrategy):
  """Read and write operations for sheets with a header row."""

  def __init__(self):
    try:
      self._pl = importlib.import_module('polars')
    except ModuleNotFoundError as e:
      raise ModuleNotFoundError(
          'Polars is not installed. Please install it with `pip install polars`'
      ) from e

  def read(self, worksheet, range_name=None):
    data = worksheet.get_values(range_name)
    return self._pl.DataFrame(data, orient='row')

  def write(self, worksheet, df, location, **kwargs):
    data = [list(r) for r in df.iter_rows()]
    worksheet.update(location, data, **kwargs)


class PolarsHeaderStorageStrategy(InteractiveSheetStorageStrategy):
  """Read and write operations for sheets without a header row."""

  def __init__(self):
    try:
      self._pl = importlib.import_module('polars')
    except ModuleNotFoundError as e:
      raise ModuleNotFoundError(
          'Polars is not installed. Please install it with `pip install polars`'
      ) from e

  def read(self, worksheet, range_name=None):
    data = worksheet.get_values(range_name)
    if not data:
      return self._pl.DataFrame()
    # Data is a list of lists, i.e.
    # [[header1, header2], [row1col1, row1col2], ...], where the first element
    # is the column names, the rest are the rows.
    columns = data[0]
    rows = data[1:]
    return self._pl.DataFrame(rows, schema=columns, orient='row')

  def write(self, worksheet, df, location, **kwargs):
    # gspread json.dumps every cell and doesn't support polars' dates, etc.
    # As a result we cast everything that is not a number to a string first.
    formatted = df.cast({operator.invert(self._pl.selectors.numeric()): str})
    data = [df.columns] + [list(r) for r in formatted.iter_rows()]
    worksheet.update(location, data, **kwargs)
