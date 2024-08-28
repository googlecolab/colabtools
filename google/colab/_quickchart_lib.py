"""Library of charts for use by quickchart."""

import base64
import dataclasses
import io

import IPython.display


# Note: lazy imports throughout due to minimizing kernel init imports.
# pylint:disable=g-import-not-at-top


@dataclasses.dataclass
class ChartData:
  title: str
  code: str


class MplChart:
  """Matplotlib chart wrapper that displays charts to PNG <image> elements."""

  def __init__(self, chart_html):
    self.chart_html = chart_html

  @classmethod
  def from_current_mpl_state(cls):
    """Creates a PNG-based chart from the current matplotlib state."""
    from matplotlib import pyplot as plt

    f = io.BytesIO()
    plt.savefig(
        f,
        bbox_inches='tight',
        # TODO: Remove when internal version is updated.
        transparent=False,
        edgecolor='white',
        facecolor='white',
    )
    plt.close()
    f.seek(0)
    png_data = f.read()
    return cls(f"""<img style="width: 180px;" src="data:image/png;base64,{
        base64.encodebytes(png_data).decode("ascii")}">""")

  def _repr_html_(self):
    return self.chart_html

  def _repr_mimebundle_(self, include=None, exclude=None):  # pylint:disable=unused-argument
    return {'text/html': self._repr_html_()}

  def display(self):
    IPython.display.display(self._repr_mimebundle_(), raw=True)


class autoviz:  # pylint:disable=invalid-name
  """Namespace to emulate top-level google.colab.autoviz.

  Exists to allow code within this module to work both with local within-module
  references for testing/rendering by direct invocation and also as
  individual notebook code snippets that have access to the `autoviz` module.
  """

  MplChart = MplChart  # pylint:disable=invalid-name


def histogram(df_name: str, colname: str, num_bins=20) -> ChartData:
  """Generates a histogram for the given data column.

  Args:
    df_name: Variable name of a dataframe.
    colname: Name of the column to plot.
    num_bins: The number of value bins.

  Returns:
    Code to generate the plot.
  """
  code = f"""from matplotlib import pyplot as plt
{df_name}[{colname!r}].plot(kind='hist', bins={num_bins}, title={colname!r})
plt.gca().spines[['top', 'right',]].set_visible(False)"""
  return ChartData(title=colname, code=code)


def categorical_histogram(df_name, colname) -> ChartData:
  """Generates a single categorical histogram.

  Args:
    df_name: Variable name of a dataframe.
    colname: The column name to plot.

  Returns:
    Code to generate the plot.
  """
  code = f"""from matplotlib import pyplot as plt
import seaborn as sns
{df_name}.groupby({colname!r}).size().plot(kind='barh', color=sns.palettes.mpl_palette('Dark2'))
plt.gca().spines[['top', 'right',]].set_visible(False)"""

  return ChartData(title=colname, code=code)


def heatmap(df_name: str, x_colname: str, y_colname: str) -> ChartData:
  """Generates a single heatmap.

  Args:
    df_name: Variable name of a dataframe.
    x_colname: The x-axis column name.
    y_colname: The y-axis column name.

  Returns:
    Code to generate the plot.
  """
  code = f"""from matplotlib import pyplot as plt
import seaborn as sns
import pandas as pd
plt.subplots(figsize=(8, 8))
df_2dhist = pd.DataFrame({{
    x_label: grp[{y_colname!r}].value_counts()
    for x_label, grp in {df_name}.groupby({x_colname!r})
}})
sns.heatmap(df_2dhist, cmap='viridis')
plt.xlabel({x_colname!r})
_ = plt.ylabel({y_colname!r})"""

  return ChartData(f'{x_colname} vs {y_colname}', code)


def swarm_plot(
    df_name: str, value_colname: str, facet_colname: str, jitter_domain_width=8
) -> ChartData:
  """Generates a single swarm plot.

  Incorporated from altair example gallery:
    https://altair-viz.github.io/gallery/stripplot.html

  Args:
    df_name: Variable name of a dataframe.
    value_colname: The value distribution column name.
    facet_colname: The faceting column name.
    jitter_domain_width: Jitter width.

  Returns:
    Code to generate the plot.
  """

  code = f"""from matplotlib import pyplot as plt
import numpy as np
import seaborn as sns
palette = sns.palettes.mpl_palette('Dark2')
facet_values = list(sorted({df_name}[{facet_colname!r}].unique()))
_, ax = plt.subplots(figsize=(1.2 * len(facet_values), 8))
ax.spines[['top', 'right']].set_visible(False)
xtick_locs = [{jitter_domain_width}*i for i in range(len(facet_values))]
for i, facet_value in enumerate(facet_values):
  color = palette[i % len(palette)]
  values = {df_name}[{df_name}[{facet_colname!r}] == facet_value][{value_colname!r}]
  r1, r2 = np.random.random(len(values)), np.random.random(len(values))
  jitter = np.sqrt(-2*np.log(r1))*np.cos(2*np.pi*r2)  # Box-Muller.
  ax.scatter(xtick_locs[i] + jitter, values, s=1.5, alpha=.8, color=color)
ax.xaxis.set_ticks(xtick_locs, facet_values, rotation='vertical')
plt.title({facet_colname!r})
_ = plt.ylabel({value_colname!r})"""

  return ChartData(f'{facet_colname} vs {value_colname}', code)


def violin_plot(
    df_name: str, value_colname: str, facet_colname: str, inner: str
) -> ChartData:
  """Generates a single violin plot.

  Args:
    df_name: Variable name of a dataframe.
    value_colname: The value distribution column name.
    facet_colname: The faceting column name.
    inner: Representation of the data in the violin interior.

  Returns:
    Code to generate the plot.
  """
  code = f"""from matplotlib import pyplot as plt
import seaborn as sns
figsize = (12, 1.2 * len({df_name}[{facet_colname!r}].unique()))
plt.figure(figsize=figsize)
sns.violinplot({df_name}, x={value_colname!r}, y={facet_colname!r}, inner={inner!r}, palette='Dark2')
sns.despine(top=True, right=True, bottom=True, left=True)"""

  return ChartData(f'{facet_colname} vs {value_colname}', code)


def value_plot(df_name: str, y: str) -> ChartData:
  """Generates a single value plot.

  Args:
    df_name: Variable name of a dataframe.
    y: The series name to plot.

  Returns:
    Code to generate the plot.
  """

  code = f"""from matplotlib import pyplot as plt
{df_name}[{y!r}].plot(kind='line', figsize=(8, 4), title={y!r})
plt.gca().spines[['top', 'right']].set_visible(False)"""

  return ChartData(y, code)


def scatter_plot(df_name: str, x_colname: str, y_colname: str) -> ChartData:
  """Generates a single scatter plot.

  Args:
    df_name: Variable name of a dataframe.
    x_colname: Column name for the X axis.
    y_colname: Column name for the Y axis.

  Returns:
    Code to generate the plot.
  """

  code = f"""from matplotlib import pyplot as plt
{df_name}.plot(kind='scatter', x={x_colname!r}, y={y_colname!r}, s=32, alpha=.8)
plt.gca().spines[['top', 'right',]].set_visible(False)"""

  return ChartData(f'{x_colname} vs {y_colname}', code)


def time_series_multiline(
    df_name: str, timelike_colname: str, value_colname: str, series_colname: str
) -> ChartData:
  """Generates a single time series plot.

  Args:
    df_name: Variable name of a dataframe.
    timelike_colname: Column name for the time based column.
    value_colname: Column name for the value column.
    series_colname: Column name for the series column.

  Returns:
    Code to generate the plot.
  """
  plot_series_impl = f"""xs = series[{timelike_colname!r}]
  ys = series[{value_colname!r}]
  """
  if value_colname == 'count()':
    plot_series_impl = f"""counted = (series[{timelike_colname!r}]
                .value_counts()
              .reset_index(name='counts')
              .rename({{'index': {timelike_colname!r}}}, axis=1)
              .sort_values({timelike_colname!r}, ascending=True))
  xs = counted[{timelike_colname!r}]
  ys = counted['counts']"""

  series_impl = """_plot_series(df_sorted, '')"""
  if series_colname:
    series_impl = f"""for i, (series_name, series) in enumerate(df_sorted.groupby({series_colname!r})):
  _plot_series(series, series_name, i)
  fig.legend(title={series_colname!r}, bbox_to_anchor=(1, 1), loc='upper left')"""

  code = f"""from matplotlib import pyplot as plt
import seaborn as sns
def _plot_series(series, series_name, series_index=0):
  palette = list(sns.palettes.mpl_palette('Dark2'))
  {plot_series_impl}
  plt.plot(xs, ys, label=series_name, color=palette[series_index % len(palette)])

fig, ax = plt.subplots(figsize=(10, 5.2), layout='constrained')
df_sorted = {df_name}.sort_values({timelike_colname!r}, ascending=True)
{series_impl}
sns.despine(fig=fig, ax=ax)
plt.xlabel({timelike_colname!r})
_ = plt.ylabel({value_colname!r})"""

  return ChartData(f'{timelike_colname} vs {value_colname}', code)
