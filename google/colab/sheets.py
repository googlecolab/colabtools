"""Helper class to build interactive sheets."""

import abc
import datetime
import google.auth
from google.colab import auth
import gspread
import IPython
import numpy as np
import pandas as pd

_gspread_client = None


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
  return frame.applymap(_clean_val).replace({np.nan: None})


def _generate_creds(unused_credentials=None):
  auth.authenticate_user()
  scopes = (
      'https://www.googleapis.com/auth/drive',
      'https://www.googleapis.com/auth/spreadsheets',
  )
  creds, _ = google.auth.default(scopes=scopes)
  return creds


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
  """

  def __init__(
      self,
      *,
      title='',
      url='',
      sheet_id='',
      df=None,
      worksheet_id=-1,
      worksheet_name='',
      credentials=None,
      include_column_headers=True,
      display=True,
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
        https://docs.google.com/spreadsheets/d/{sheet_id}.
      df: If provided, populate the sheet with this data
      worksheet_id: If provided, load data from this worksheet_id. Note -
        worksheet_id indicates which worksheet (tab) to use. Worksheet_id is the
        optional query param, `gid` in the sheets URL i.e.
        https://docs.google.com/spreadsheets/d/{sheet_id}?gid={worksheet_id}.
      worksheet_name: If provided, load data from this worksheet_name
      credentials: If provided, use these oauth credentials.
      include_column_headers: If True, assume the first row of the sheet is a
        header column for both reads and writes.
      display: If True, displays the embedded sheet in the cell output.
    """
    if sum([bool(url), bool(sheet_id), bool(title)]) > 1:
      raise ValueError(
          'Expected either a `url`, `sheet_id` or `title` but got more than'
          ' one.'
      )

    if worksheet_id >= 0 and worksheet_name:
      raise ValueError('Expected `worksheet_id` or `worksheet_name` got both.')
    if worksheet_id < 0 and not worksheet_name:
      worksheet_id = 0

    if sheet_id:
      url = f'https://docs.google.com/spreadsheets/d/{sheet_id}'
    self._credentials = credentials
    self._ensure_gspread_client()

    self.sheet = self._load_or_create_sheet(url, title)

    if worksheet_name:
      self.worksheet = self.sheet.worksheet(worksheet_name)
    else:
      self.worksheet = self.sheet.get_worksheet(worksheet_id)

    self.url = f'{self.sheet.url}#gid={self.worksheet.id}'
    # Printing the URL gives the user a convenient handle to the pointer page.
    print(self.url)
    self.embedded_url = (
        f'{self.url}/edit?rm=embedded?usp=sharing?widget=true&amp;headers=false'
    )

    if include_column_headers:
      self.storage_strategy = HeaderStorageStrategy()
    else:
      self.storage_strategy = HeaderlessStorageStrategy()

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

  def as_df(self):
    """as_df fetches the data in the current worksheet and returns a new dataframe.

    Returns:
      a pandas Dataframe with the latest data from the current worksheet
    """
    self._ensure_gspread_client()
    data = self.storage_strategy.read(self.worksheet)
    return pd.DataFrame(data)

  def update(self, df):
    """Update clears the sheet and replaces it with the provided dataframe.

    Args:
      df: the source data
    """
    self._ensure_gspread_client()
    self.worksheet.clear()
    self.storage_strategy.write(self.worksheet, _to_frame(df))

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
  def write(self, worksheet, df):
    pass


class HeaderlessStorageStrategy(InteractiveSheetStorageStrategy):
  """Read and write operations for sheets with a header row."""

  def read(self, worksheet):
    data = worksheet.get_values()
    return pd.DataFrame(data)

  def write(self, worksheet, df):
    data = [list(r) for _, r in df.iterrows()]
    worksheet.update('', data)


class HeaderStorageStrategy(InteractiveSheetStorageStrategy):
  """Read and write operations for sheets without a header row."""

  def read(self, worksheet):
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

  def write(self, worksheet, df):
    data = [list(df.columns)] + [list(r) for _, r in df.iterrows()]
    worksheet.update('', data)
