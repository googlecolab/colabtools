"""Library of charts for use by quickchart."""

import altair as alt


def histogram(df, colname, maxbins=20, width=100, height=50):
  """Generates a histogram for the given data column.

  Args:
    df: (pd.DataFrame) A dataframe.
    colname: (str) Name of the column to plot.
    maxbins: (int) The max number of value bins.
    width: (int) The width (pixels) of a single histogram plot.
    height: (int) The height (pixels) of a single histogram plot.

  Returns:
    (alt.Chart) A grid of histogram plots as a single chart.
  """
  distribution = (
      alt.Chart(df)
      .mark_bar()
      .encode(
          x=alt.X(
              colname,
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
  )
  return distribution


def categorical_histogram(df, colname, width=100, height=50, colormap='dark2'):
  """Generates a single categorical histogram.

  Args:
    df: (pd.DataFrame) A dataframe.
    colname: (str) The column name to plot.
    width: (int) Plot width.
    height: (int) Plot height.
    colormap: (str) Colormap to use for differentiating categories.

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
              'index', scale=alt.Scale(scheme=colormap), legend=None
          ),
      )
      .properties(
          width=width,
          height=height,
          title=colname,
      )
  )
  return hist


def heatmap(df, x_colname, y_colname):
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


def swarm_plot(df, value_colname, facet_colname, height=150, width=150):
  """Generates a single swarm plot.

  Incorporated from altair example gallery:
    https://altair-viz.github.io/gallery/stripplot.html

  Args:
    df: (pd.DataFrame) A dataframe.
    value_colname: (str) The value distribution column name.
    facet_colname: (str) The faceting column name.
    height: (int) Plot height.
    width: (int) Plot width.

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
          height=height,
          width=width / num_facets,
      )
      .transform_calculate(
          # Box-Muller transform for Gaussian-distributed jitter.
          jitter='sqrt(-2*log(random()))*cos(2*PI*random())'
      )
      .configure_facet(spacing=0)
      .configure_view(stroke=None)
  )
  return chart


def value_plot(df, y, sort_ascending=False, width=100, height=50):
  """Generates a single value plot.

  Args:
    df: (pd.DataFrame) A dataframe.
    y: (str) The series name to plot.
    sort_ascending: (bool) Sort the series (ascending) before plotting?
    width: (int) Chart width.
    height: (int) Chart height.

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
          width=width,
          height=height,
          title=y,
      )
  )


def linked_scatter_plots(
    df,
    colname_pairs,
    color='steelblue',
    deselected_color='lightgray',
    opacity=0.8,
    deselected_opacity=0.4,
    width=150,
    height=150,
):
  """Generates a grid of linked scatter plots.

  Args:
    df: (pd.DataFrame) A dataframe.
    colname_pairs: (iterable<str, str>) A sequence of (x-axis, y-axis) column
      name pairs to use for each heatmap.
    color: (str) Default color of scatter plot points.
    deselected_color: (str) Alternative color when points are deselected.
    opacity: (float) Opacity of scatter plot points.
    deselected_opacity: (float) Alternative opacity when points are deselected.
    width: (int) Width of each scatter plot.
    height: (int) Height of each scatter plot.

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
              alt.value(color),
              alt.value(deselected_color),
          ),
          opacity=alt.condition(
              interval,
              alt.value(opacity),
              alt.value(deselected_opacity),
          ),
      )
      .properties(
          selection=interval,
          width=width,
          height=height,
      )
  )
  return alt.hconcat(*[scatter.encode(x=x, y=y) for x, y in colname_pairs])
