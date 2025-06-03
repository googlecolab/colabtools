"""Functions for SQL cells interacting with BigQuery."""

import re
from typing import Any, Iterable, Mapping, TypedDict

from bigframes import dtypes
import bigframes.pandas as bpd
from google.auth import credentials
from google.auth import exceptions as auth_exceptions
import IPython

# Extracts the line and column number from a dry-run error message.
_LINE_COLUMN_REGEX = re.compile(r'\[(\d+):(\d+)\]', re.MULTILINE)


class TableReference(TypedDict):
  """A reference to a BigQuery table."""

  project_id: str
  dataset_id: str
  table_id: str


# TODO: b/421959485 - Use NotRequired once for optional fields.
class TableSchemaEntry(TypedDict):
  """An item in the schema of a BigQuery table."""

  name: str
  field_type: str
  mode: str | None = None
  description: str | None = None


class ValidationError(TypedDict):
  """SQL validation error information."""

  message: str
  line: int | None = None
  column: int | None = None


class ValidationSuccess(TypedDict):
  """Successful SQL validation."""

  bytes_processed: int
  compiled_sql: str
  tables: list[TableReference]
  schema: list[TableSchemaEntry]


class ValidationFailure(TypedDict):
  """Failed SQL validation."""

  authorization_failed: bool
  errors: list[ValidationError]


ValidationResult = ValidationSuccess | ValidationFailure


def set_credentials(
    creds: credentials.Credentials | None = None,
    project_id: str | None = None,
):
  """Sets the credentials and project ID to use for BigFrames requests.

  This will close the current BigFrames session and set the credentials and
  project ID to use for BigFrames requests.

  Args:
    creds: The credentials to use for BigQuery requests.
    project_id: The project ID to use for BigQuery requests.
  """
  bpd.close_session()
  bpd.options.bigquery.project = project_id
  bpd.options.bigquery.credentials = creds


def validate(sql: str) -> ValidationResult:
  """Validates the SQL syntax and returns a ValidationResult object.

  This method is intended to be used by the Colab FE to utilize BigQuery's
  dry-run validation engine.

  Args:
    sql: The SQL to validate.

  Returns:
    ValidationResult object.
  """
  try:
    # pylint: disable=protected-access
    dry_run_series = bpd.get_global_session()._read_gbq_colab(
        sql, dry_run=True, pyformat_args=_get_ipython_locals()
    )
    bytes_processed = 0
    try:
      bytes_processed = int(dry_run_series.get('totalBytesProcessed', 0))
    except ValueError:
      pass
    compiled_sql = dry_run_series.get('dispatchedSql', '')
    referenced_tables = dry_run_series.get('referencedTables', None) or []
    column_types: dict[str, dtypes.Dtype] = (
        dry_run_series.get('columnDtypes', None) or dict()
    )
    tables = [
        TableReference(
            project_id=t.get('projectId', None),
            dataset_id=t.get('datasetId', None),
            table_id=t.get('tableId', None),
        )
        for t in referenced_tables
    ]
    schema = [
        TableSchemaEntry(
            name=name, field_type=field_type.name, mode=None, description=None
        )
        for name, field_type in column_types.items()
    ]
    result = ValidationSuccess(
        bytes_processed=bytes_processed,
        compiled_sql=compiled_sql,
        tables=tables,
        schema=schema,
    )
  except auth_exceptions.GoogleAuthError as e:
    validation_error = ValidationError(message=str(e), line=None, column=None)
    result = ValidationFailure(
        errors=[validation_error], authorization_failed=True
    )
  except Exception as e:  # pylint: disable=broad-exception-caught
    result = ValidationFailure(
        errors=_get_validation_errors(e), authorization_failed=False
    )

  return result


def run(sql: str) -> bpd.DataFrame:
  """Executes the SQL and returns the BigQuery DataFrame."""
  with bpd.option_context('display.progress_bar', None):
    # pylint: disable=protected-access
    return bpd.get_global_session()._read_gbq_colab(
        sql, pyformat_args=_get_ipython_locals()
    )


def _get_validation_errors(e: Exception) -> list[ValidationError]:
  """Returns a list of ValidationErrors from the given exception."""
  validation_errors: list[ValidationError] = []
  if hasattr(e, 'errors') and isinstance(e.errors, Iterable):
    # Create a ValidationError for each error message.
    for error in e.errors:
      if isinstance(error, Mapping) and 'message' in error:
        message, line, column = error['message'], None, None
        try:
          line, column = map(int, _LINE_COLUMN_REGEX.search(message).groups())
        except Exception:  # pylint: disable=broad-exception-caught
          # Should not occur based on regex, but added for safety.
          pass
        validation_errors.append(
            ValidationError(message=message, line=line, column=column)
        )

  if not validation_errors:
    # If no errors were found, return the Exception message.
    validation_errors.append(
        ValidationError(message=str(e), line=None, column=None)
    )

  return validation_errors


def _get_ipython_locals() -> dict[str, Any]:
  """Returns the IPython session locals or an empty dict if not available."""
  ipython = IPython.get_ipython()
  if not ipython:
    return dict()
  return ipython.user_ns
