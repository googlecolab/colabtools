"""Chart ranking utilities."""

import itertools
import warnings

from google.colab import _quickchart_dtypes
import numpy as np
import pandas as pd
import scipy.stats


def rank_histograms(df, colnames, rank_depth=None, filter_threshold=0.1):
  """Ranks histograms by interestingness.

  Args:
    df: (pd.DataFrame) A dataframe.
    colnames: (iter<str>) Numeric columns to consider.
    rank_depth: (int) The max number of charts to consider when ranking; None
      indicates that all possible charts should be evaluated.
    filter_threshold: (float) A score threshold below which charts are filtered.

  Returns:
    (iter<str>) Ranked colnames.
  """
  scored_cols = [(score_dist(df[c]), c) for c in colnames[:rank_depth]]
  return [
      c
      for score, c in sorted(scored_cols, reverse=True)
      if score > filter_threshold
  ]


def rank_scatter(df, colnames, rank_depth=None, filter_threshold=0.1):
  """Ranks scatter plots by interestingness.

  Args:
    df: (pd.DataFrame) A dataframe.
    colnames: (iter<str>) Numeric columns for either x or y axes.
    rank_depth: (int) The max number of charts to consider when ranking; None
      indicates that all possible charts should be evaluated.
    filter_threshold: (float) A score threshold below which charts are filtered.

  Returns:
    (iter<(str, str)>) Ranked (x, y) colname tuples.
  """
  scored_pairs = sorted(
      (
          (score_correlation(df[a], df[b]), (a, b))
          for a, b in select_first_k_pairs(colnames, k=rank_depth)
      ),
      reverse=True,
  )
  return [pair for score, pair in scored_pairs if score > filter_threshold]


def rank_value_plots(df, colnames, rank_depth=None, filter_threshold=0.1):
  """Ranks value plots by interestingness.

  Args:
    df: (pd.DataFrame) A dataframe.
    colnames: (iter<str>) Value dimension columns.
    rank_depth: (int) The max number of charts to consider when ranking; None
      indicates that all possible charts should be evaluated.
    filter_threshold: (float) A score threshold below which charts are filtered.

  Returns:
    (iter<str>) Ranked colnames.
  """
  x = np.arange(len(df))
  return [
      colname
      for score, colname in sorted(
          ((score_correlation(x, df[c]), c) for c in colnames[:rank_depth]),
          reverse=True,
      )
      if score > filter_threshold
  ]


def rank_time_series_plots(
    df,
    time_colnames,
    numeric_colnames,
    categorical_colnames,
    rank_depth=None,
    filter_threshold=0.1,
):
  """Ranks time series plots by interestingness.

  Args:
    df: (pd.DataFrame) A dataframe.
    time_colnames: (iter<str>) Time dimension columns.
    numeric_colnames: (iter<str>) Value dimension columns.
    categorical_colnames: (iter<str>) Facet/series dimension columns.
    rank_depth: (int) The max number of charts to consider when ranking; None
      indicates that all possible charts should be evaluated.
    filter_threshold: (float) A score threshold below which charts are filtered.

  Returns:
    (iter<(str, str, str)>) Ranked (time, value, series) colname tuples.
  """
  scored = sorted(
      (
          (score_time_series(df, t, y, facet), (t, y, facet))
          for t, y, facet in select_time_series_cols(
              time_colnames,
              numeric_colnames,
              categorical_colnames,
              k=rank_depth,
          )
      ),
      reverse=True,
  )
  return [args for score, args in scored if score > filter_threshold]


def rank_heatmaps(df, colnames, rank_depth=None, filter_threshold=0.05):
  """Ranks heatmaps by interestingness.

  Args:
    df: (pd.DataFrame) A dataframe.
    colnames: (iter<str>) Heatmap dimension columns.
    rank_depth: (int) The max number of charts to consider when ranking; None
      indicates that all possible charts should be evaluated.
    filter_threshold: (float) A score threshold below which charts are filtered.

  Returns:
    (iter<(str, str)>) Ranked (x, y) colname tuples.
  """
  scored = sorted(
      [
          (score_dist2d(df, x, y), (x, y))
          for x, y in select_first_k_pairs(colnames, k=rank_depth)
      ],
      reverse=True,
  )
  return [pair for score, pair in scored if score > filter_threshold]


def rank_faceted_distributions(
    df, value_colnames, facet_colnames, rank_depth=None, filter_threshold=0.1
):
  """Ranks faceted distributions by interestingness.

  Args:
    df: (pd.DataFrame) A dataframe.
    value_colnames: (iter<str>) Value dimension columns.
    facet_colnames: (iter<str>) Facet/series dimension columns.
    rank_depth: (int) The max number of charts to consider when ranking; None
      indicates that all possible charts should be evaluated.
    filter_threshold: (float) A score threshold below which charts are filtered.

  Returns:
    (iter<str, str>) Ranked (value, facet) colname tuples.
  """
  scored = sorted(
      (
          (
              score_faceted_distribution(df, value_colname, facet_colname),
              (value_colname, facet_colname),
          )
          for (value_colname, facet_colname) in select_faceted_numeric_cols(
              value_colnames, facet_colnames, k=rank_depth
          )
      ),
      reverse=True,
  )
  return [
      (value_colname, facet_colname)
      for score, (value_colname, facet_colname) in scored
      if score > filter_threshold
  ]


def select_first_k_pairs(colnames, k=None):
  """Selects the first k pairs of column names, sequentially.

  e.g., ['a', 'b', 'c'] => [('a', b'), ('b', 'c')] for k=2

  Args:
    colnames: (iterable<str>) Column names from which to generate pairs.
    k: (int) The number of column pairs.

  Returns:
    (list<(str, str)>) A k-length sequence of column name pairs.
  """
  return itertools.islice(itertools.combinations(colnames, 2), k)


def select_faceted_numeric_cols(numeric_cols, categorical_cols, k=None):
  """Selects numeric columns and corresponding categorical facets.

  Args:
    numeric_cols: (iterable<str>) Available numeric columns.
    categorical_cols: (iterable<str>) Available categorical columns.
    k: (int) The number of column pairs to select.

  Returns:
    (iter<(str, str)>) Prioritized sequence of (numeric, categorical) column
    pairs.
  """
  return itertools.islice(itertools.product(numeric_cols, categorical_cols), k)


def select_time_series_cols(time_cols, numeric_cols, categorical_cols, k=None):
  """Selects combinations of colnames that can be plotted as time series.

  Args:
    time_cols: (iter<str>) Available time-like columns.
    numeric_cols: (iter<str>) Available numeric columns.
    categorical_cols: (iter<str>) Available categorical columns.
    k: (int) The number of combinations to select.

  Returns:
    (iter<(str, str, str)>) Prioritized sequence of (time, value, series)
    colname combinations.
  """
  numeric_cols = [c for c in numeric_cols if c not in time_cols]
  numeric_aggregates = ['count()']
  if not categorical_cols:
    categorical_cols = [None]
  return itertools.islice(
      itertools.product(
          time_cols, numeric_cols + numeric_aggregates, categorical_cols
      ),
      k,
  )


def unevenness(x, epsilon=1e-6, scale_factor=0.95):
  """Score the unevenness of a sequence of values.

  Args:
    x: (np.array) Sequence of values to score.
    epsilon: (float) Small value to avoid divide by zero.
    scale_factor: (float) How much to discount scores for longer sequences.

  Returns:
    Value (float) in [0, +) with larger values indicating unevenness and values
    near zero indicating a flat sequence.
  """
  x = np.array(x) + epsilon  # Avoid divide by zero when normalizing.
  # Normalize input and take Euclidean distance to uniform distribution.
  dist = np.linalg.norm(((x) / (x.sum())) - np.ones(len(x)) / len(x), 2)
  # Scale the distance based upon the number of input values.
  return dist * scale_factor ** len(x)


def resampled_unevenness(x, resolution=10):
  """Unevenness of a sequence resampled via piece-wise aggregation."""
  resampled = (
      np.array([chunk.mean() for chunk in np.array_split(x, resolution)])
      if len(x) > resolution
      else x
  )
  return unevenness(resampled)


def score_dist(series, bins=10):
  with warnings.catch_warnings():
    warnings.filterwarnings('ignore', 'Precision loss')
    skew = scipy.stats.skew(get_histogram_values(series, bins=bins))
  return 0.0 if np.isnan(skew) else abs(skew)


def score_faceted_distribution(df, value_colname, facet_colname):
  return np.array(
      [score_dist(grp[value_colname]) for _, grp in df.groupby(facet_colname)]
  ).mean()


def score_dist2d(df, x_colname, y_colname):
  values = get_2dhist(df, x_colname, y_colname).values.flatten()
  values = values[~np.isnan(values)]  # Filter nans.
  return scipy.stats.entropy(
      values, np.ones(len(values))
  )  # KL divergence from uniform.


def score_correlation(series1, series2):
  # Pearson's r in [-1, +1], with 1.0 and -1.0 implying linear correlation.
  r, _ = scipy.stats.pearsonr(series1, series2)
  return 1 - abs(r)  # Values close to zero indicate near-perfect correlation.


def score_time_series(df, time_colname, value_colname, facet_colname):
  """Scores a time series by interestingness."""
  if facet_colname:
    return np.array([
        score_time_series(grp, time_colname, value_colname, None)
        for _, grp in df.groupby(facet_colname)
    ]).mean()

  if value_colname == 'count()':
    y = df[time_colname].value_counts()
    x = pd.Series(y.index.values)
  else:
    x, y = df[time_colname], df[value_colname]
  if len(x.unique()) == 1 or len(y.unique()) == 1:
    return 0.0
  return score_correlation(x, y)


def get_histogram_values(series, bins=20):
  if _quickchart_dtypes.is_categorical(series):
    return series.value_counts().to_numpy()
  bar_heights, _ = np.histogram(series, bins=bins)
  return bar_heights


def get_2dhist(df, x_colname, y_colname):
  return pd.DataFrame({
      x_label: grp[y_colname].value_counts()
      for x_label, grp in df.groupby(x_colname)
  })
