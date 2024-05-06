"""Summarize properties of each column in a pandas DataFrame."""

import warnings
import numpy as np
import pandas as pd

_MAX_DATAFRAME_ROWS = 100000
_MAX_DATAFRAME_COLS = 20


def summarize_dataframe(df, variable_name):
  """Summarizes a dataframe."""

  columns = _summarize_columns(df)
  return {
      "name": variable_name,
      "rows": len(df),
      "fields": columns,
  }


def _check_type(dtype: str, value):
  """Cast value to right type to ensure it is JSON serializable."""
  if np.isnan(value):
    return None
  if "float" in str(dtype):
    return float(value)
  elif "int" in str(dtype):
    return int(value)
  else:
    return value


# Inspired by:
# https://github.com/microsoft/lida/blob/9bb26c0adb56cab2d7c5d49ad96bc14e204c87ec/lida/components/summarizer.py#L34
def _summarize_columns(df: pd.DataFrame, n_samples: int = 3):
  """Summarize properties of each column in a pandas DataFrame."""
  properties_list = []
  # Include index if it is a named index.
  df_with_columns = df.reset_index() if df.index.name else df
  for column_name, column in df_with_columns.items():
    dtype = column.dtype
    properties = {}
    if dtype in (int, float, complex):
      properties["dtype"] = "number"
      properties["std"] = _check_type(dtype, column.std())
      properties["min"] = _check_type(dtype, column.min())
      properties["max"] = _check_type(dtype, column.max())

    elif dtype == bool:
      properties["dtype"] = "boolean"
    elif dtype == object:
      # Check if the string column can be cast to a valid datetime
      try:
        with warnings.catch_warnings():
          warnings.simplefilter("ignore")
          pd.to_datetime(column, errors="raise")
          if (
              not column.empty
              and column.dtype.kind == "O"
              and isinstance(column[0], str)
          ):
            properties["dtype"] = "object"
          else:
            properties["dtype"] = "date"
      except (TypeError, ValueError):
        try:
          # Check if the string column has a limited number of values
          if column.nunique() / len(column) < 0.5:
            properties["dtype"] = "category"
          else:
            properties["dtype"] = "string"
        except TypeError:
          properties["dtype"] = str(dtype)
    elif isinstance(column, pd.CategoricalDtype):
      properties["dtype"] = "category"
    elif pd.api.types.is_datetime64_any_dtype(column):
      properties["dtype"] = "date"
    else:
      properties["dtype"] = str(dtype)

    # add min max if dtype is date
    if properties["dtype"] == "date":
      try:
        properties["min"] = column.min()
        properties["max"] = column.max()
      except TypeError:
        cast_date_col = pd.to_datetime(column, errors="coerce")
        properties["min"] = cast_date_col.min()
        properties["max"] = cast_date_col.max()
    # Add additional properties to the output dictionary
    try:
      nunique = column.nunique()
      properties["num_unique_values"] = nunique
    except TypeError:
      pass
    if "samples" not in properties:
      try:
        non_null_values = column[column.notnull()].unique()
        n_samples = min(n_samples, len(non_null_values))
        samples = (
            pd.Series(non_null_values)
            .sample(n_samples, random_state=42)
            .tolist()
        )
        properties["samples"] = samples
      except TypeError:
        # Samples is optional here.
        pass
    properties["semantic_type"] = ""
    properties["description"] = ""
    properties_list.append({"column": column_name, "properties": properties})

  return properties_list
