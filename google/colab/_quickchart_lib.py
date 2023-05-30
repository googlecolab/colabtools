"""Library of charts for use by quickchart."""

import altair as alt

# Note: pyformat disabled for this module since these are user-facing code
# snippets that are meant to be more notebook-style per b/283014273#comment8.
# pyformat: disable
# pylint:disable=missing-function-docstring


def histogram(df, colname, maxbins=20, width=100, height=50):
  return (alt.Chart(df).mark_bar()
          .encode(
              x=alt.X(colname, bin=alt.Bin(maxbins=maxbins)),
              y=alt.Y('count()', axis=alt.Axis(title='count')),
          )
          .properties(width=width, height=height))  #  Pixels.


def categorical_histogram(df, colname, width=100, height=50, colormap='dark2'):
  chart_data = df[colname].value_counts().reset_index(name='count')
  return (alt.Chart(chart_data).mark_bar()
          .encode(
              x='count', y=alt.Y('index', title=''),
              color=alt.Color(
                  'index', scale=alt.Scale(scheme=colormap), legend=None))
          .properties(width=width, height=height, title=colname))  # Pixels.


def heatmap(df, x_colname, y_colname):
  return (alt.Chart(df).mark_rect()
          .encode(x=x_colname, y=y_colname, color='count()'))


# Incorporated from altair example gallery:
#   https://altair-viz.github.io/gallery/stripplot.html
def swarm_plot(df, value_colname, facet_colname, height=150, width=150):
  value_min, value_max = df[value_colname].min(), df[value_colname].max()
  num_facets = len(df[facet_colname].unique())
  value_colname += ':Q'
  facet_colname += ':N'
  return (alt.Chart(df).mark_circle(size=8)
          .encode(
              x=alt.X('jitter:Q', title=None,
                      axis=alt.Axis(
                          values=[0], ticks=True, grid=False, labels=False)),
              y=alt.Y(value_colname,
                      scale=alt.Scale(domain=[value_min, value_max])),
              color=alt.Color(facet_colname, legend=None),
              column=alt.Column(
                  facet_colname,
                  header=alt.Header(
                      labelAngle=-90, titleOrient='top', labelOrient='bottom',
                      labelAlign='right', labelPadding=3)))
          .properties(height=height, width=width / num_facets)
          .transform_calculate(
              jitter='sqrt(-2*log(random()))*cos(2*PI*random())')  # Box-Muller.
          .configure_facet(spacing=0)
          .configure_view(stroke=None))


def value_plot(df, y, sort_ascending=False, width=100, height=50):
  if sort_ascending:
    df = df.sort_values(y).reset_index(drop=True)
  return (alt.Chart(df.reset_index()).mark_line()
          .encode(x=alt.X('index', title=''), y=alt.X(y, title='value'))
          .properties(width=width, height=height, title=y))


def linked_scatter_plots(
    df, colname_pairs, color='steelblue', deselected_color='lightgray',
    opacity=0.8, deselected_opacity=0.4, width=150, height=150):
  interval = alt.selection_interval()
  scatter = (alt.Chart(df).mark_circle()
             .encode(
                 color=alt.condition(
                     interval, alt.value(color), alt.value(deselected_color)),
                 opacity=alt.condition(
                     interval, alt.value(opacity),
                     alt.value(deselected_opacity)))
             .properties(
                 selection=interval, width=width, height=height))
  return alt.hconcat(*[scatter.encode(x=x, y=y) for x, y in colname_pairs])
