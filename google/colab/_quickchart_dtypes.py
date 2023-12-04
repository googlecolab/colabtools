"""Chart datatype inference utilities."""

import collections.abc
import logging

import numpy as np


_CATEGORICAL_DTYPES = (
    np.dtype('object'),
    np.dtype('bool'),
)
_DEFAULT_DATETIME_DTYPE = np.dtype('datetime64[ns]')  # a.k.a. "<M8[ns]".
_DATETIME_DTYPES = (_DEFAULT_DATETIME_DTYPE,)
_DATETIME_DTYPE_KINDS = ('M',)  # More general set of datetime dtypes.
_DATETIME_COLNAME_PATTERNS = (
    'date',
    'datetime',
    'time',
    'timestamp',
)  # Prefix/suffix matches.
_DATETIME_COLNAMES = ('dt', 't', 'ts', 'year')  # Exact matches.
_EXPECTED_DTYPES = _CATEGORICAL_DTYPES + _DATETIME_DTYPES
_CATEGORICAL_LARGE_SIZE_THRESHOLD = 8  # Facet-friendly size limit.


def is_categorical(series):
  return (
      series.dtype in _CATEGORICAL_DTYPES
      and len(series.unique()) <= _CATEGORICAL_LARGE_SIZE_THRESHOLD
  )


def classify_dtypes(
    df,
    categorical_dtypes=_CATEGORICAL_DTYPES,
    datetime_dtypes=_DATETIME_DTYPES,
    datetime_dtype_kinds=_DATETIME_DTYPE_KINDS,
    categorical_size_threshold=_CATEGORICAL_LARGE_SIZE_THRESHOLD,
):
  """Classifies each dataframe series into a datatype group.

  Args:
    df: (pd.DataFrame) A dataframe.
    categorical_dtypes: (iterable<str>) Categorical data types.
    datetime_dtypes: (iterable<str>) Datetime data types.
    datetime_dtype_kinds: (iterable<str>) Datetime dtype.kind values.
    categorical_size_threshold: (int) The max number of unique values for a
      given categorical to be considered "small".

  Returns:
    ({str: list<str>}) A dict mapping a dtype name to the corresponding
    column names.
  """
  # Lazy import to avoid loading pandas and transitive deps on kernel init.
  import pandas as pd  # pylint: disable=g-import-not-at-top
  from pandas.api.types import is_numeric_dtype  # pylint: disable=g-import-not-at-top

  dtypes = (
      pd.DataFrame(df.dtypes, columns=['colname_dtype'])
      .reset_index()
      .rename(columns={'index': 'colname'})
  )

  filtered_cols = []
  numeric_cols = []
  cat_cols = []
  datetime_cols = []
  timelike_cols = []
  singleton_cols = []
  for colname, colname_dtype in zip(dtypes.colname, dtypes.colname_dtype):
    if not all(df[colname].apply(pd.api.types.is_hashable)):
      filtered_cols.append(colname)
    elif len(df[colname].unique()) <= 1:
      singleton_cols.append(colname)
    elif colname_dtype in categorical_dtypes:
      cat_cols.append(colname)
    elif (colname_dtype in datetime_dtypes) or (
        colname_dtype.kind in datetime_dtype_kinds
    ):
      datetime_cols.append(colname)
    elif is_numeric_dtype(colname_dtype):
      numeric_cols.append(colname)
    else:
      filtered_cols.append(colname)
  if filtered_cols:
    logging.warning(
        'Quickchart encountered unexpected dtypes in columns: "%r"',
        (filtered_cols,),
    )

  small_cat_cols, large_cat_cols = [], []
  for colname in cat_cols:
    if len(df[colname].unique()) <= categorical_size_threshold:
      small_cat_cols.append(colname)
    else:
      large_cat_cols.append(colname)

  def _matches_datetime_pattern(colname):
    colname = str(colname).lower()
    return any(
        colname.startswith(p) or colname.endswith(p)
        for p in _DATETIME_COLNAME_PATTERNS
    ) or any(colname == c for c in _DATETIME_COLNAMES)

  for colname in df.columns:
    if (
        _matches_datetime_pattern(colname)
        or _is_monotonically_increasing_numeric(df[colname])
    ) and _all_values_scalar(df[colname]):
      timelike_cols.append(colname)

  return {
      'numeric': numeric_cols,
      'categorical': small_cat_cols,
      'large_categorical': large_cat_cols,
      'datetime': datetime_cols,
      'timelike': timelike_cols,
      'singleton': singleton_cols,
      'filtered': filtered_cols,
  }


def _is_monotonically_increasing_numeric(series):
  # Pandas extension dtypes do not extend numpy's dtype and will fail if passed
  # into issubdtype.
  if not isinstance(series.dtype, np.dtype):
    return False
  return np.issubdtype(series.dtype.base, np.number) and np.all(
      np.array(series)[:-1] <= np.array(series)[1:]
  )


def _all_values_scalar(series):
  def _is_non_scalar(x):
    return isinstance(x, collections.abc.Iterable) and not isinstance(
        x, (bytes, str)
    )

  return not any(_is_non_scalar(x) for x in series)
