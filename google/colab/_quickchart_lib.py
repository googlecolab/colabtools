"""Library of charts for use by quickchart."""

import altair as alt

_COLORMAP = 'dark2'
_DEFAULT_COLOR = 'steelblue'
_DESELECTED_COLOR = 'lightgray'
_DEFAULT_OPACITY = 0.8
_DESELECTED_OPACITY = 0.4
_LARGE_PLOT_SIZE = 150
_MAX_PLOT_COLUMNS = 5
_NUM_HIST_BINS = 20
_PLOT_WIDTH = 100
_PLOT_HEIGHT = 50
_SECTION_TITLE_KWS = {
    'fontSize': 12,
    'color': 'gray',
}


def categorical_histograms(
    df,
    colnames,
    **kwargs,
):
  """Generates a grid of categorical histograms.

  Args:
    df: (pd.DataFrame) A dataframe.
    colnames: (iterable<str>) The column names for which to generate histograms.
    **kwargs: (dict) Chart grid styling kwargs.

  Returns:
    (alt.Chart) A grid of histograms as a single chart.
  """
  charts = [_categorical_histogram(df, c) for c in colnames]
  return _as_chart_grid(charts, **kwargs)


def heatmaps(
    df,
    colname_pairs,
    **kwargs,
):
  """Generates a grid of heatmaps.

  Args:
    df: (pd.Dataframe) A dataframe.
    colname_pairs: (iterable<str, str>) Sequence of (x-axis, y-axis) column name
      pairs.
    **kwargs: (dict) Chart grid styling kwargs.

  Returns:
    (alt.Chart) A grid of heatmaps as a single chart.
  """
  charts = [_heatmap(df, x, y) for x, y in colname_pairs]
  return _as_chart_grid(charts, **kwargs)


def histograms(
    df,
    colnames,
    maxbins=_NUM_HIST_BINS,
    width=_PLOT_WIDTH,
    height=_PLOT_HEIGHT,
    max_columns=_MAX_PLOT_COLUMNS,
    title='',
    title_kws=None,
):
  """Generates a grid of histograms for the given data columns.

  Args:
    df: (pd.DataFrame) A dataframe.
    colnames: (iterable<str>) A sequence of column names that should correspond
      to numeric series.
    maxbins: (int) The max number of value bins.
    width: (int) The width (pixels) of a single histogram plot.
    height: (int) The height (pixels) of a single histogram plot.
    max_columns: (int) The maximum number of plots to include per row.
    title: (str) The title for the grid of plots.
    title_kws: (dict) Title styling options.

  Returns:
    (alt.Chart) A grid of histogram plots as a single chart.
  """
  title_kws = title_kws or _SECTION_TITLE_KWS
  distributions = (
      alt.Chart(df)
      .mark_bar()
      .encode(
          x=alt.X(
              alt.repeat('repeat'),
              bin=alt.Bin(
                  maxbins=maxbins,
              ),
          ),
          y=alt.Y('count()', axis=alt.Axis(title='count')),
      )
      .properties(
          width=width,
          height=height,
      )
      .repeat(
          repeat=colnames,
          columns=max_columns,
      )
  )
  return (
      alt.vconcat(distributions)
      .configure_title(**title_kws)
      .properties(
          title=title,
      )
  )


def linked_scatter_plots(df, colname_pairs, **kwargs):
  """Generates a grid of linked scatter plots.

  Args:
    df: (pd.DataFrame) A dataframe.
    colname_pairs: (iterable<str, str>) A sequence of (x-axis, y-axis) column
      name pairs to use for each heatmap.
    **kwargs: (dict) Chart grid styling kwargs.

  Returns:
    (alt.Chart) A single chart containing one or more linked scatter plots.
  """
  interval = alt.selection_interval()
  scatter = (
      alt.Chart(df)
      .mark_circle()
      .encode(
          color=alt.condition(
              interval,
              alt.value(_DEFAULT_COLOR),
              alt.value(_DESELECTED_COLOR),
          ),
          opacity=alt.condition(
              interval,
              alt.value(_DEFAULT_OPACITY),
              alt.value(_DESELECTED_OPACITY),
          ),
      )
      .properties(
          selection=interval,
          width=_LARGE_PLOT_SIZE,
          height=_LARGE_PLOT_SIZE,
      )
  )
  charts = [scatter.encode(x=x, y=y) for x, y in colname_pairs]
  return _as_chart_grid(charts, **kwargs)


def swarm_plots(
    df,
    value_facet_colnames,
    **kwargs,
):
  """Generates a grid of swarm plots.

  Args:
    df: (pd.DataFrame) A dataframe.
    value_facet_colnames: (iterable<str, str>) Colname pairs of the form
      (numeric value, categorical facet).
    **kwargs: (dict) Chart grid styling kwargs.

  Returns:
    (alt.Chart) The grid of swarm plots as a single chart.
  """
  charts = [
      _swarm_plot(df, value, facet) for value, facet in value_facet_colnames
  ]
  return (
      _as_chart_grid(charts, **kwargs)
      .configure_facet(spacing=0)
      .configure_view(stroke=None)
  )


def value_plots(
    df,
    colnames,
    **kwargs,
):
  """Generates a grid of value plots.

  Args:
    df: (pd.DataFrame) A dataframe.
    colnames: (sequence<str>) The column names to include in the grid of plots.
    **kwargs: (dict) Chart grid styling kwargs.

  Returns:
    (alt.Chart) The grid of plots as a single chart.
  """
  charts = [_value_plot(df, c) for c in colnames]
  return _as_chart_grid(charts, **kwargs)


def _as_chart_grid(
    charts,
    max_row_size=_MAX_PLOT_COLUMNS,
    title='',
    title_kws=None,
):
  """Renders a sequence of charts as a grid of charts.

  Args:
    charts: (iterable<alt.Chart) Sequence of charts.
    max_row_size: (int) The maximum number of plots to include in a single row.
    title: (str) The title for the grid of plots.
    title_kws: (dict) Title style keywords.

  Returns:
    (alt.Chart) A grid of histograms as a single chart.
  """
  title_kws = title_kws or _SECTION_TITLE_KWS
  combined_charts = (
      alt.vconcat(
          *[
              alt.hconcat(*row).resolve_scale(color='independent')
              for row in _chunked(charts, max_row_size)
          ]
      )
      .properties(
          title=title,
      )
      .configure_title(**title_kws)
  )
  return combined_charts


def _categorical_histogram(df, colname):
  """Generates a single categorical histogram.

  Args:
    df: (pd.DataFrame) A dataframe.
    colname: (str) The column name to plot.

  Returns:
    (alt.Chart) A histogram.
  """
  chart_data = df[colname].value_counts().reset_index(name='count')
  hist = (
      alt.Chart(chart_data)
      .mark_bar()
      .encode(
          x='count',
          y=alt.Y('index', title=''),
          color=alt.Color(
              'index', scale=alt.Scale(scheme=_COLORMAP), legend=None
          ),
      )
      .properties(
          width=_PLOT_WIDTH,
          height=_PLOT_HEIGHT,
          title=colname,
      )
  )
  return hist


def _chunked(seq, chunk_size):
  """Partitions the sequence into equally-sized slices.

  If the sequence length is not evenly divisible by the chunk size, the
  remainder is included rather than truncated.

  Args:
    seq: (iterable) A sequence.
    chunk_size: (int) The size of each sequence partition.

  Yields:
    (sequence<sequence<T>>) A sequence of chunks.
  """
  # Lazy import to avoid loading on kernel init.
  # TODO(b/275732775): switch back to itertools.pairwise when possible.
  import more_itertools  # pylint: disable=g-import-not-at-top

  for start, end in more_itertools.pairwise(
      list(range(0, len(seq), chunk_size)) + [len(seq)]
  ):
    yield seq[start:end]


def _heatmap(df, x_colname, y_colname):
  """Generates a single heatmap.

  Args:
    df: (pd.DataFrame) A dataframe.
    x_colname: (str) The x-axis column name.
    y_colname: (str) The y-axis column name.

  Returns:
    (alt.Chart) A heatmap plot.
  """
  chart = (
      alt.Chart(df)
      .mark_rect()
      .encode(x=x_colname, y=y_colname, color='count()')
  )
  return chart


def _swarm_plot(df, value_colname, facet_colname):
  """Generates a single swarm plot.

  Incorporated from altair example gallery:
    https://altair-viz.github.io/gallery/stripplot.html

  Args:
    df: (pd.DataFrame) A dataframe.
    value_colname: (str) The value distribution column name.
    facet_colname: (str) The faceting column name.

  Returns:
    (alt.Chart) A swarm plot.
  """
  value_min, value_max = df[value_colname].min(), df[value_colname].max()
  num_facets = len(df[facet_colname].unique())
  value_colname += ':Q'
  facet_colname += ':N'
  chart = (
      alt.Chart(df)
      .mark_circle(size=8)
      .encode(
          x=alt.X(
              'jitter:Q',
              title=None,
              axis=alt.Axis(values=[0], ticks=True, grid=False, labels=False),
          ),
          y=alt.Y(
              value_colname,
              scale=alt.Scale(domain=[value_min, value_max]),
          ),
          color=alt.Color(facet_colname, legend=None),
          column=alt.Column(
              facet_colname,
              header=alt.Header(
                  labelAngle=-90,
                  titleOrient='top',
                  labelOrient='bottom',
                  labelAlign='right',
                  labelPadding=3,
              ),
          ),
      )
      .properties(
          height=_LARGE_PLOT_SIZE,
          width=_LARGE_PLOT_SIZE / num_facets,
      )
      .transform_calculate(
          # Box-Muller transform for Gaussian-distributed jitter.
          jitter='sqrt(-2*log(random()))*cos(2*PI*random())'
      )
  )
  return chart


def _value_plot(df, y, sort_ascending=False):
  """Generates a single value plot.

  Args:
    df: (pd.DataFrame) A dataframe.
    y: (str) The series name to plot.
    sort_ascending: (bool) Sort the series (ascending) before plotting?

  Returns:
    (alt.Chart) A value plot.
  """
  if sort_ascending:
    df = df.sort_values(y).reset_index(drop=True)
  return (
      alt.Chart(df.reset_index())
      .mark_line()
      .encode(
          x=alt.X('index', title=''),
          y=alt.X(y, title='value'),
      )
      .properties(
          width=_PLOT_WIDTH,
          height=_PLOT_HEIGHT,
          title=y,
      )
  )
