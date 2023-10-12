"""Library of charts for use by quickchart."""

import base64
import io

import IPython.display
import numpy as np


# Note: lazy imports throughout due to minimizing kernel init imports.
# pylint:disable=g-import-not-at-top


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
        # TODO(b/210783561): Remove when internal version is updated.
        transparent=False,
        edgecolor='white',
        facecolor='white',
    )
    plt.close()
    f.seek(0)
    png_data = f.read()
    return cls(f"""<img src="data:image/png;base64,{
        base64.encodebytes(png_data).decode("ascii")}">
        <script></script>""")

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


# Note: pyformat disabled for this module since these are user-facing code
# snippets that are meant to be more notebook-style per b/283014273#comment8.
# pyformat: disable
# pylint:disable=missing-function-docstring


# NOTE: All functions below must have a `figscale` keyword arg.


def histogram(df, colname, num_bins=20, figscale=1):
  from matplotlib import pyplot as plt
  df[colname].plot(kind='hist', bins=num_bins, title=colname, figsize=(8*figscale, 4*figscale))
  plt.gca().spines[['top', 'right',]].set_visible(False)
  plt.tight_layout()
  return autoviz.MplChart.from_current_mpl_state()


def categorical_histogram(df, colname, figscale=1, mpl_palette_name='Dark2'):
  from matplotlib import pyplot as plt
  import seaborn as sns
  df.groupby(colname).size().plot(kind='barh', color=sns.palettes.mpl_palette(mpl_palette_name), figsize=(8*figscale, 4.8*figscale))
  plt.gca().spines[['top', 'right',]].set_visible(False)
  return autoviz.MplChart.from_current_mpl_state()


def heatmap(df, x_colname, y_colname, figscale=1, mpl_palette_name='viridis'):
  from matplotlib import pyplot as plt
  import seaborn as sns
  import pandas as pd
  plt.subplots(figsize=(8 * figscale, 8 * figscale))
  df_2dhist = pd.DataFrame({
      x_label: grp[y_colname].value_counts()
      for x_label, grp in df.groupby(x_colname)
  })
  sns.heatmap(df_2dhist, cmap=mpl_palette_name)
  plt.xlabel(x_colname)
  plt.ylabel(y_colname)
  return autoviz.MplChart.from_current_mpl_state()


def swarm_plot(df, value_colname, facet_colname, figscale=1, mpl_palette_name='Dark2', jitter_domain_width=8):
  from matplotlib import pyplot as plt
  import seaborn as sns
  palette = sns.palettes.mpl_palette(mpl_palette_name)
  facet_values = list(sorted(df[facet_colname].unique()))
  figsize = (1.2 * figscale * len(facet_values), 8 * figscale)
  _, ax = plt.subplots(figsize=figsize)
  ax.spines[['top', 'right']].set_visible(False)
  xtick_locs = [jitter_domain_width*i for i in range(len(facet_values))]
  for i, facet_value in enumerate(facet_values):
    color = palette[i % len(palette)]
    values = df[df[facet_colname] == facet_value][value_colname]
    r1, r2 = np.random.random(len(values)), np.random.random(len(values))
    jitter = np.sqrt(-2*np.log(r1))*np.cos(2*np.pi*r2)  # Box-Muller.
    ax.scatter(xtick_locs[i] + jitter, values, s=1.5, alpha=.8, color=color)
  ax.xaxis.set_ticks(xtick_locs, facet_values, rotation='vertical')
  plt.title(facet_colname)
  plt.ylabel(value_colname)
  return autoviz.MplChart.from_current_mpl_state()


def violin_plot(df, value_colname, facet_colname, figscale=1, mpl_palette_name='Dark2', **kwargs):
  from matplotlib import pyplot as plt
  import seaborn as sns
  figsize = (12 * figscale, 1.2 * figscale * len(df[facet_colname].unique()))
  plt.figure(figsize=figsize)
  sns.violinplot(df, x=value_colname, y=facet_colname, palette=mpl_palette_name, **kwargs)
  sns.despine(top=True, right=True, bottom=True, left=True)
  return autoviz.MplChart.from_current_mpl_state()


def value_plot(df, y, figscale=1):
  from matplotlib import pyplot as plt
  df[y].plot(kind='line', figsize=(8 * figscale, 4 * figscale), title=y)
  plt.gca().spines[['top', 'right']].set_visible(False)
  plt.tight_layout()
  return autoviz.MplChart.from_current_mpl_state()


def scatter_plot(df, x_colname, y_colname, figscale=1, alpha=.8):
  from matplotlib import pyplot as plt
  plt.figure(figsize=(6 * figscale, 6 * figscale))
  df.plot(kind='scatter', x=x_colname, y=y_colname, s=(32 * figscale), alpha=alpha)
  plt.gca().spines[['top', 'right',]].set_visible(False)
  plt.tight_layout()
  return autoviz.MplChart.from_current_mpl_state()


def time_series_multiline(df, timelike_colname, value_colname, series_colname, figscale=1, mpl_palette_name='Dark2'):
  from matplotlib import pyplot as plt
  import seaborn as sns
  figsize = (10 * figscale, 5.2 * figscale)
  palette = list(sns.palettes.mpl_palette(mpl_palette_name))
  def _plot_series(series, series_name, series_index=0):
    if value_colname == 'count()':
      counted = (series[timelike_colname]
                 .value_counts()
                 .reset_index(name='counts')
                 .rename({'index': timelike_colname}, axis=1)
                 .sort_values(timelike_colname, ascending=True))
      xs = counted[timelike_colname]
      ys = counted['counts']
    else:
      xs = series[timelike_colname]
      ys = series[value_colname]
    plt.plot(xs, ys, label=series_name, color=palette[series_index % len(palette)])

  fig, ax = plt.subplots(figsize=figsize, layout='constrained')
  df = df.sort_values(timelike_colname, ascending=True)
  if series_colname:
    for i, (series_name, series) in enumerate(df.groupby(series_colname)):
      _plot_series(series, series_name, i)
    fig.legend(title=series_colname, bbox_to_anchor=(1, 1), loc='upper left')
  else:
    _plot_series(df, '')
  sns.despine(fig=fig, ax=ax)
  plt.xlabel(timelike_colname)
  plt.ylabel(value_colname)
  return autoviz.MplChart.from_current_mpl_state()
