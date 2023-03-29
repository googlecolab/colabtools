"""Automated chart generation for data frames."""
import itertools
import logging

import numpy as np


_MAX_ROWS = 5000  # Limit of underlying vega-lite schema.
_CATEGORICAL_DTYPES = (
    np.dtype('object'),
    np.dtype('bool'),
)
_DATETIME_DTYPES = (np.dtype('datetime64[ns]'),)  # a.k.a. "<M8[ns]"
_EXPECTED_DTYPES = _CATEGORICAL_DTYPES + _DATETIME_DTYPES
_CATEGORICAL_LARGE_SIZE_THRESHOLD = 8  # Facet-friendly size limit.


def find_charts(
    df, max_chart_instances=None, max_rows=_MAX_ROWS, random_state=0
):
  """Finds charts compatible with dtypes of the given data frame.

  Args:
    df: (pd.DataFrame) A dataframe.
    max_chart_instances: (int) For a single chart type, the max number instances
      to generate.
    max_rows: (int) The maximum number of rows to sample from the dataframe; if
      more than `max_rows` are available, the dataframe is sampled, truncated,
      and re-sorted according to the dataframe's original index.
    random_state: (int) The random state to use when downsampling datframes that
      exceed the `max_rows` threshold.

  Returns:
    (iterable<alt.Chart>) A sequence of chart objects.
  """
  # Lazy import to avoid loading altair and transitive deps on kernel init.
  from google.colab import _quickchart_lib  # pylint: disable=g-import-not-at-top

  if len(df) > max_rows:
    df = df.sample(n=max_rows, random_state=random_state).sort_index()
  dtype_groups = _classify_dtypes(df)
  numeric_cols = dtype_groups['numeric']
  categorical_cols = dtype_groups['categorical']
  charts = []

  if numeric_cols:
    charts += [
        _quickchart_lib.histograms(
            df, numeric_cols[:max_chart_instances], title='Distributions'
        ),
        _quickchart_lib.value_plots(
            df, numeric_cols[:max_chart_instances], title='Values'
        ),
    ]
  if categorical_cols:
    charts += [
        _quickchart_lib.categorical_histograms(
            df,
            categorical_cols[:max_chart_instances],
            title='Categorical distributions',
        ),
    ]

  if len(numeric_cols) > 2:
    charts += [
        _quickchart_lib.linked_scatter_plots(
            df,
            _select_first_k_pairs(numeric_cols, k=max_chart_instances),
            title='2-d distributions',
        )
    ]

  if len(categorical_cols) > 2:
    charts += [
        _quickchart_lib.heatmaps(
            df,
            _select_first_k_pairs(categorical_cols, k=max_chart_instances),
            title='Heatmaps',
        )
    ]

  if categorical_cols and numeric_cols:
    charts += [
        _quickchart_lib.swarm_plots(
            df,
            _select_faceted_numeric_cols(
                numeric_cols, categorical_cols, k=max_chart_instances
            ),
            title='Swarm plots',
        )
    ]

  return charts


def _select_first_k_pairs(colnames, k=None):
  """Selects the first k pairs of column names, sequentially.

  e.g., ['a', 'b', 'c'] => [('a', b'), ('b', 'c')] for k=2

  Args:
    colnames: (iterable<str>) Column names from which to generate pairs.
    k: (int) The number of column pairs.

  Returns:
    (list<(str, str)>) A k-length sequence of column name pairs.
  """
  # Lazy import to avoid loading on kernel init.
  # TODO(b/275732775): switch back to itertools.pairwise when possible.
  import more_itertools  # pylint: disable=g-import-not-at-top

  return itertools.islice(more_itertools.pairwise(colnames), k)


def _select_faceted_numeric_cols(numeric_cols, categorical_cols, k=None):
  """Selects numeric columns and corresponding categorical facets.

  Args:
    numeric_cols: (iterable<str>) Available numeric columns.
    categorical_cols: (iterable<str>) Available categorical columns.
    k: (int) The number of column pairs to select.

  Returns:
    (list<(str, str)>) Prioritized sequence of (numeric, categorical) column
    pairs.
  """
  return itertools.islice(itertools.product(numeric_cols, categorical_cols), k)


def _classify_dtypes(
    df,
    categorical_dtypes=_CATEGORICAL_DTYPES,
    datetime_dtypes=_DATETIME_DTYPES,
    categorical_size_threshold=_CATEGORICAL_LARGE_SIZE_THRESHOLD,
):
  """Classifies each dataframe series into a datatype group.

  Args:
    df: (pd.DataFrame) A dataframe.
    categorical_dtypes: (iterable<str>) Categorical data types.
    datetime_dtypes: (iterable<str>) Datetime data types.
    categorical_size_threshold: (int) The max number of unique values for a
      given categorical to be considered "small".

  Returns:
    ({str: list<str>}) A dict mapping a dtype name to the corresponding
    column names.
  """
  # Lazy import to avoid loading pandas and transitive deps on kernel init.
  import pandas as pd  # pylint: disable=g-import-not-at-top

  dtypes = (
      pd.DataFrame(df.dtypes, columns=['colname_dtype'])
      .reset_index()
      .rename(columns={'index': 'colname'})
  )

  filtered_cols = []
  numeric_cols = []
  cat_cols = []
  datetime_cols = []
  for colname, colname_dtype in zip(dtypes.colname, dtypes.colname_dtype):
    if colname_dtype in categorical_dtypes:
      cat_cols.append(colname)
    elif colname_dtype in datetime_dtypes:
      datetime_cols.append(colname)
    elif np.issubdtype(colname_dtype, np.number):
      numeric_cols.append(colname)
    else:
      filtered_cols.append(colname)
  if filtered_cols:
    logging.warning(
        'Quickchart encountered unexpected dtypes: "%r"', (filtered_cols,)
    )

  singleton_cols, small_cat_cols, large_cat_cols = [], [], []
  for colname in cat_cols:
    num_cat_values = len(df[colname].unique())
    if num_cat_values <= 1:
      singleton_cols.append(colname)
    elif num_cat_values <= categorical_size_threshold:
      small_cat_cols.append(colname)
    else:
      large_cat_cols.append(colname)

  kept_numeric_cols = []
  for colname in numeric_cols:
    if len(df[colname].unique()) <= 1:
      singleton_cols.append(colname)
    else:
      kept_numeric_cols.append(colname)

  return {
      'numeric': kept_numeric_cols,
      'categorical': small_cat_cols,
      'large_categorical': large_cat_cols,
      'datetime': datetime_cols,
      'singleton': singleton_cols,
      'filtered': filtered_cols,
  }


def _get_axis_bounds(series, padding_percent=0.05, zero_rtol=1e-3):
  """Gets the min/max axis bounds for a given data series.

  Args:
    series: (pd.Series) A data series.
    padding_percent: (float) The amount of padding to add to the minimal domain
      extent as a percentage of the domain size.
    zero_rtol: (float) If either min or max bound is within this relative
      tolerance to zero, don't add padding for aesthetics.

  Returns:
    (<float> min_bound, <float> max_bound)
  """
  min_bound, max_bound = series.min(), series.max()
  padding = (max_bound - min_bound) * padding_percent
  if not np.allclose(0, min_bound, rtol=zero_rtol):
    min_bound -= padding
  if not np.allclose(0, max_bound, rtol=zero_rtol):
    max_bound += padding
  return min_bound, max_bound
