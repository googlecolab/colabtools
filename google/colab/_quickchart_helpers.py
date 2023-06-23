"""Supporting code for quickchart functionality."""

import inspect
import textwrap
import uuid as _uuid

from google.colab import _quickchart_lib
import IPython.display
import matplotlib as mpl
import numpy as np


_MPL_STYLE_OPTIONS = (
    ('axes.labelpad', 1.0),
    ('axes.linewidth', 0.4),
    ('font.size', 8),
    ('legend.fontsize', 8),
    ('legend.title_fontsize', 8),
)
_VIOLIN_PLOT_STICK_MAX_ROWS = 500


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
  for i in range(0, len(seq), chunk_size):
    yield seq[i : i + chunk_size]


class ChartSectionType:
  HISTOGRAM = 'histogram'
  VALUE_PLOT = 'value_plot'
  HEATMAP = 'heatmap'
  LINKED_SCATTER = 'linked_scatter'
  CATEGORICAL_HISTOGRAM = 'categorical_histogram'
  FACETED_DISTRIBUTION = 'faceted_distribution'
  TIME_SERIES_LINE_PLOT = 'time_series_line_plot'


class ChartSection:
  """Grouping of charts and other displayable objects."""

  def __init__(self, section_type, charts, displayables):
    self._section_type = section_type
    self._charts = charts
    self._displayables = displayables

  @property
  def section_type(self):
    return self._section_type

  @property
  def charts(self):
    return self._charts

  def display(self):
    for d in self._displayables:
      d.display()


class SectionTitle:
  """Section title used for delineating chart sections."""

  def __init__(self, title):
    self.title = title

  def display(self):
    IPython.display.display(self)

  def _repr_html_(self):
    return textwrap.dedent(f"""\
        <h4 class="colab-quickchart-section-title">{self.title}</h4>
        <style>
          .colab-quickchart-section-title {{
              clear: both;
          }}
        </style>""")


class DataframeRegistry:
  """Dataframe registry for charts-with-code that may be displayed."""

  def __init__(self):
    self._df_chart_registry = {}

  def register_df_varname(self, df):
    """Registers a given dataframe.

    Equivalent dataframes (as determined by hash value) will receive the same
    name on repeated requests.

    Args:
      df: (pd.DataFrame) A dataframe.

    Returns:
      (str) A unique^* variable name for the dataframe.
      (^* modulo unlikely hash collisions)
    """
    df_name = f'df_{abs(hash(df.values.tobytes()))}'
    self._df_chart_registry[df_name] = df
    return df_name

  def __getitem__(self, df_varname):
    return self._df_chart_registry[df_varname]


class ChartWithCode:
  """Wrapper for chart that also knows how to get its own code."""

  def __init__(self, df, plot_func, args, kwargs, df_registry):
    self._df = df
    self._df_registry = df_registry
    self._df_varname = self._df_registry.register_df_varname(df)

    self._plot_func = plot_func
    self._args = args
    self._kwargs = kwargs

    self._chart_id = f'chart-{str(_uuid.uuid4())}'
    with mpl.rc_context(dict(_MPL_STYLE_OPTIONS)):
      self._chart = plot_func(df, *args, **kwargs)

  @property
  def chart_id(self):
    return self._chart_id

  def display(self):
    """Displays the chart within a notebook context."""
    IPython.display.display(self)

  def get_code(self):
    """Gets the code and associated dependencies + context for a given chart."""

    plot_func_src = inspect.getsource(self._plot_func)
    plot_invocation = textwrap.dedent(
        """\
        chart = {plot_func}({df_varname}, *{args}, **{kwargs})
        chart""".format(
            plot_func=self._plot_func.__name__,
            args=str(self._args),
            kwargs=str(self._kwargs),
            df_varname=self._df_varname,
        )
    )

    chart_src = textwrap.dedent("""\
        import numpy as np
        from google.colab import autoviz
        {df_varname} = autoviz.get_registered_df('{df_varname}')
        """.format(df_varname=self._df_varname))
    chart_src += '\n'
    chart_src += plot_func_src
    chart_src += '\n'
    chart_src += plot_invocation
    return chart_src

  def _repr_html_(self):
    """Gets the HTML representation of the chart."""

    chart_html = self._chart._repr_mimebundle_()['text/html']  # pylint:disable = protected-access
    script_start = chart_html.find('<script')
    return f"""\
      <div class="colab-quickchart-chart-with-code" id="{self._chart_id}">
        {chart_html[:script_start]}
      </div>
      {chart_html[script_start:]}
      <script type="text/javascript">
        (() => {{
          const chartElement = document.getElementById("{self._chart_id}");
          async function getCodeForChartHandler(event) {{
            const chartCodeResponse =  await google.colab.kernel.invokeFunction(
                'getCodeForChart', ["{self._chart_id}"], {{}});
            const responseJson = chartCodeResponse.data['application/json'];
            await google.colab.notebook.addCell(responseJson.code, 'code');
          }}
          chartElement.onclick = getCodeForChartHandler;
        }})();
      </script>
      <style>
        .colab-quickchart-chart-with-code  {{
            display: block;
            float: left;
            border: 1px solid transparent;
        }}

        .colab-quickchart-chart-with-code:hover {{
            cursor: pointer;
            border: 1px solid #aaa;
        }}
      </style>"""

  def __repr__(self):
    return self.get_code()


def histograms_section(df, colnames, df_registry):
  """Generates a section of histograms.

  Args:
    df: (pd.DataFrame) A dataframe.
    colnames: (iterable<str>) The column names for which to generate plots.
    df_registry: (DataframeRegistry) Registry to use for dataframe lookups.

  Returns:
    (ChartSection) A chart section containing histograms.
  """
  return _chart_section(
      ChartSectionType.HISTOGRAM,
      df,
      _quickchart_lib.histogram,
      colnames,
      {},
      df_registry,
      'Distributions',
  )


def value_plots_section(df, colnames, df_registry):
  """Generates a section of value plots.

  Args:
    df: (pd.DataFrame) A dataframe.
    colnames: (iterable<str>) The column names for which to generate plots.
    df_registry: (DataframeRegistry) Registry to use for dataframe lookups.

  Returns:
    (ChartSection) A chart section containing value plots.
  """
  return _chart_section(
      ChartSectionType.VALUE_PLOT,
      df,
      _quickchart_lib.value_plot,
      colnames,
      {},
      df_registry,
      'Values',
  )


def categorical_histograms_section(df, colnames, df_registry):
  """Generates a section of categorical histograms.

  Args:
    df: (pd.DataFrame) A dataframe.
    colnames: (iterable<str>) The column names for which to generate histograms.
    df_registry: (DataframeRegistry) Registry to use for dataframe lookups.

  Returns:
    (ChartSection) A chart section containing categorical histograms.
  """
  return _chart_section(
      ChartSectionType.CATEGORICAL_HISTOGRAM,
      df,
      _quickchart_lib.categorical_histogram,
      colnames,
      {},
      df_registry,
      'Categorical distributions',
  )


def heatmaps_section(df, colname_pairs, df_registry):
  """Generates a section of heatmaps.

  Args:
    df: (pd.DataFrame) A dataframe.
    colname_pairs: (iterable<str, str>) Sequence of (x-axis, y-axis) column name
      pairs to plot.
    df_registry: (DatframeRegistry) Registry to use for dataframe lookups.

  Returns:
    (ChartSection) A chart section containing heatmaps.
  """
  return _chart_section(
      ChartSectionType.HEATMAP,
      df,
      _quickchart_lib.heatmap,
      colname_pairs,
      {},
      df_registry,
      '2-d categorical distributions',
  )


def linked_scatter_section(df, colname_pairs, df_registry):
  """Generates a section of linked scatter plots.

  Args:
    df: (pd.DataFrame) A dataframe.
    colname_pairs: (iterable<str, str>) Sequence of (x-colname, y-colname) pairs
      to plot.
    df_registry: (DataframeRegistry) Registry to use for dataframe lookups.

  Returns:
    (ChartSection) A chart section containing linked scatter plots.
  """
  return _chart_section(
      ChartSectionType.LINKED_SCATTER,
      df,
      _quickchart_lib.scatter_plots,
      [[list(colname_pairs)]],
      {},
      df_registry,
      '2-d distributions',
  )


def faceted_distributions_section(df, colname_pairs, df_registry):
  """Generates a section of faceted distribution plots.

  Args:
    df: (pd.DataFrame) A dataframe.
    colname_pairs: (iterable<str, str>) Sequence of (value, facet) column name
      pairs to plot.
    df_registry: (DataframeRegistry) Registry to use for dataframe lookups.

  Returns:
    (ChartSection) A chart section.
  """
  return _chart_section(
      ChartSectionType.FACETED_DISTRIBUTION,
      df,
      _quickchart_lib.violin_plot,
      colname_pairs,
      {'inner': 'stick' if len(df) < _VIOLIN_PLOT_STICK_MAX_ROWS else 'box'},
      df_registry,
      'Faceted distributions',
  )


def time_series_line_plots_section(df, colname_pairs, df_registry):
  """Generates a section of time series line plots.

  Args:
    df: (pd.DataFrame) A dataframe.
    colname_pairs: (iterable<str, str>) Sequence of (time-like colname, series
      colname) pairs to plot; if series colname is None, only a single series is
      plotted.
    df_registry: (DataframeRegistry) Registry to use for dataframe lookups.

  Returns:
    (ChartSection) A chart section containing time series line plots.
  """
  return _chart_section(
      ChartSectionType.TIME_SERIES_LINE_PLOT,
      df,
      _quickchart_lib.time_series_multiline,
      colname_pairs,
      {},
      df_registry,
      'Time series',
  )


def _chart_section(
    section_type, df, plot_func, args_per_chart, kwargs, df_registry, title
):
  """Generates a chart section.

  Args:
    section_type: (str) Chart section type.
    df: (pd.DataFrame) A dataframe.
    plot_func: (Function) Rendering function mapping (df, *args, **kwargs) =>
      <IPython displayble>
    args_per_chart: (iterable<args>) Sequence of arguments to pass for each
      chart in the section.
    kwargs: (dict) Common set of keyword args to pass for each chart.
    df_registry: (DataframeRegistry) Registry to use for dataframe lookups.
    title: (str) Section title to display.

  Returns:
    (ChartSection) A chart section.
  """
  charts = [
      ChartWithCode(
          df, plot_func, np.atleast_1d(args).tolist(), kwargs, df_registry
      )
      for args in args_per_chart
  ]
  return ChartSection(
      section_type=section_type,
      charts=charts,
      displayables=([SectionTitle(title)] + charts),
  )
