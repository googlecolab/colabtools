# Copyright 2025 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Colab functions for SQL cells interacting with BigQuery."""

from typing import Iterable, Mapping, TypedDict

from google.auth import credentials
from google.auth import exceptions as auth_exceptions
from google.cloud import bigquery


__all__ = ['validate_sql']

# BigQuery client to use for all requests from functions in this module.
# TODO: b/414366687 - Consider thread-safe approach.
_client: bigquery.Client | None = None


class TableReference(TypedDict):
  """A reference to a BigQuery table."""

  project_id: str
  dataset_id: str
  table_id: str


class TableSchemaEntry(TypedDict):
  """An item in the schema of a BigQuery table."""

  name: str
  field_type: str
  mode: str
  description: str


class ValidationError(TypedDict):
  """SQL validation error information."""

  messages: list[str]


class ValidationSuccess(TypedDict):
  """Successful SQL validation."""

  bytes_processed: int
  tables: list[TableReference]
  schema: list[TableSchemaEntry]


class ValidationFailure(TypedDict):
  """Failed SQL validation."""

  authorization_failed: bool
  error: ValidationError


ValidationResult = ValidationSuccess | ValidationFailure


def set_credentials(
    creds: credentials.Credentials | None = None,
    project_id: str | None = None,
):
  """Sets the credentials and project ID to use for BigQuery requests.

  This resets the internal Client object used by the other functions in this
  module.

  Args:
    creds: The credentials to use for BigQuery requests.
    project_id: The project ID to use for BigQuery requests.
  """
  global _client
  _client = bigquery.Client(project=project_id, credentials=creds)


def _get_client() -> bigquery.Client:
  """Returns the client to use for BigQuery requests."""
  global _client
  if not _client:
    _client = bigquery.Client()
  return _client


def validate_sql(sql: str) -> ValidationResult:
  """Validates the SQL syntax and returns a ValidationResult object.

  This method is intended to be used by the Colab FE to utilize BigQuery's
  dry-run validation engine.

  Args:
    sql: The SQL to validate.

  Returns:
    ValidationResult object.
  """
  try:
    validation_job = _get_client().query(
        sql, job_config=bigquery.job.QueryJobConfig(dry_run=True)
    )
    tables = [
        TableReference(
            project_id=t.project,
            dataset_id=t.dataset_id,
            table_id=t.table_id,
        )
        for t in validation_job.referenced_tables
    ]
    schema = [
        TableSchemaEntry(
            name=f.name,
            field_type=f.field_type,
            mode=f.mode,
            description=f.description,
        )
        for f in validation_job.schema
    ]
    result = ValidationSuccess(
        bytes_processed=validation_job.total_bytes_processed,
        tables=tables,
        schema=schema,
    )
  except auth_exceptions.GoogleAuthError as e:
    validation_error = ValidationError(messages=[str(e)])
    result = ValidationFailure(
        error=validation_error, authorization_failed=True
    )
  except Exception as e:  # pylint: disable=broad-exception-caught
    validation_error = ValidationError(messages=[str(e)])
    # Join all error messages if multiple errors are present.
    if hasattr(e, 'errors') and isinstance(e.errors, Iterable):
      error_messages = []
      for error in e.errors:
        if isinstance(error, Mapping) and 'message' in error:
          error_messages.append(error['message'])
      validation_error['messages'] = error_messages
    result = ValidationFailure(
        error=validation_error, authorization_failed=False
    )

  return result
