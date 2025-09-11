import unittest
from unittest import mock

from bigframes import dtypes
import bigframes.pandas as bpd
from google.auth import credentials
from google.auth import exceptions as auth_exceptions
from google.colab.sql import bigquery
import IPython
import pandas

_QUERY = 'SELECT * FROM `bigquery-public-data.samples.shakespeare`'


class QueryJobError(Exception):
  """Exception class to reflect an invalid BigQuery query."""

  def __init__(self, message, errors):
    super().__init__(message)
    self.errors = errors


class ValidateTest(unittest.TestCase):

  def setUp(self):
    super().setUp()
    bpd.options.bigquery.project = None
    bpd.options.bigquery.credentials = None
    self.mock_read_gbq_colab = self.enterContext(
        mock.patch.object(bpd, '_read_gbq_colab')
    )

  def test_validate_sql_passes(self):
    dry_run_result = pandas.Series({
        'totalBytesProcessed': '1000',
        'referencedTables': [
            {
                'projectId': 'bigquery-public-data',
                'datasetId': 'samples',
                'tableId': 'shakespeare',
            },
        ],
        'columnDtypes': {
            'word_count': dtypes.INT_DTYPE,
            'word': dtypes.STRING_DTYPE,
        },
        'dispatchedSql': _QUERY,
    })
    self.mock_read_gbq_colab.return_value = dry_run_result
    expected = bigquery.ValidationSuccess(
        bytes_processed=1000,
        compiled_sql=_QUERY,
        tables=[
            bigquery.TableReference(
                project_id='bigquery-public-data',
                dataset_id='samples',
                table_id='shakespeare',
            )
        ],
        schema=[
            bigquery.TableSchemaEntry(
                name='word_count',
                field_type='Int64',
                mode=None,
                description=None,
            ),
            bigquery.TableSchemaEntry(
                name='word',
                field_type='string',
                mode=None,
                description=None,
            ),
        ],
    )

    self.assertEqual(expected, bigquery.validate(_QUERY))

    self.mock_read_gbq_colab.assert_called_once_with(
        _QUERY, dry_run=True, pyformat_args={}
    )

  @mock.patch.object(IPython, 'get_ipython')
  def test_validate_sql_with_pyformat_args(self, mock_get_ipython):
    query = 'SELECT {column} FROM {table}'
    user_ns = {
        'column': 'name',
        'table': 'bigquery-public-data.samples.shakespeare',
    }
    dispatched_sql = f'SELECT {user_ns["column"]} FROM {user_ns["table"]}'
    mock_get_ipython.return_value.user_ns = user_ns
    dry_run_result = pandas.Series({
        'totalBytesProcessed': '1000',
        'referencedTables': [
            {
                'projectId': 'bigquery-public-data',
                'datasetId': 'samples',
                'tableId': 'shakespeare',
            },
        ],
        'columnDtypes': {
            'word_count': dtypes.INT_DTYPE,
            'word': dtypes.STRING_DTYPE,
        },
        'dispatchedSql': dispatched_sql,
    })
    self.mock_read_gbq_colab.return_value = dry_run_result
    expected = bigquery.ValidationSuccess(
        bytes_processed=1000,
        compiled_sql=dispatched_sql,
        tables=[
            bigquery.TableReference(
                project_id='bigquery-public-data',
                dataset_id='samples',
                table_id='shakespeare',
            )
        ],
        schema=[
            bigquery.TableSchemaEntry(
                name='word_count',
                field_type='Int64',
                mode=None,
                description=None,
            ),
            bigquery.TableSchemaEntry(
                name='word',
                field_type='string',
                mode=None,
                description=None,
            ),
        ],
    )

    self.assertEqual(expected, bigquery.validate(query))

    self.mock_read_gbq_colab.assert_called_once_with(
        query, dry_run=True, pyformat_args=user_ns
    )

  def test_validate_sql_with_empty_result(self):
    dry_run_result = pandas.Series({})
    self.mock_read_gbq_colab.return_value = dry_run_result
    expected = bigquery.ValidationSuccess(
        bytes_processed=0,
        compiled_sql='',
        tables=[],
        schema=[],
    )

    self.assertEqual(expected, bigquery.validate(_QUERY))

    self.mock_read_gbq_colab.assert_called_once_with(
        _QUERY, dry_run=True, pyformat_args={}
    )

  def test_validate_sql_with_invalid_bytes_processed(self):
    dry_run_result = pandas.Series({
        'totalBytesProcessed': '100,000',
        'referencedTables': [
            {
                'projectId': 'bigquery-public-data',
                'datasetId': 'samples',
                'tableId': 'shakespeare',
            },
            {
                'projectId': 'test-project',
                'datasetId': 'test-dataset',
                'tableId': 'my-table',
            },
        ],
        'columnDtypes': {
            'col1': dtypes.BOOL_DTYPE,
            'col2': dtypes.DATE_DTYPE,
            'col3': dtypes.DATETIME_DTYPE,
            'col4': dtypes.FLOAT_DTYPE,
        },
    })
    self.mock_read_gbq_colab.return_value = dry_run_result
    expected = bigquery.ValidationSuccess(
        bytes_processed=0,
        compiled_sql='',
        tables=[
            bigquery.TableReference(
                project_id='bigquery-public-data',
                dataset_id='samples',
                table_id='shakespeare',
            ),
            bigquery.TableReference(
                project_id='test-project',
                dataset_id='test-dataset',
                table_id='my-table',
            ),
        ],
        schema=[
            bigquery.TableSchemaEntry(
                name='col1',
                field_type='boolean',
                mode=None,
                description=None,
            ),
            bigquery.TableSchemaEntry(
                name='col2',
                field_type='date32[day][pyarrow]',
                mode=None,
                description=None,
            ),
            bigquery.TableSchemaEntry(
                name='col3',
                field_type='timestamp[us][pyarrow]',
                mode=None,
                description=None,
            ),
            bigquery.TableSchemaEntry(
                name='col4',
                field_type='Float64',
                mode=None,
                description=None,
            ),
        ],
    )

    self.assertEqual(expected, bigquery.validate(_QUERY))

    self.mock_read_gbq_colab.assert_called_once_with(
        _QUERY, dry_run=True, pyformat_args={}
    )

  @mock.patch.object(bpd, 'close_session')
  def test_validate_sql_with_credentials(self, mock_close_session):
    creds = credentials.AnonymousCredentials()
    project_id = 'some-project-id'

    self.assertIsNone(bpd.options.bigquery.project)
    self.assertIsNone(bpd.options.bigquery.credentials)

    bigquery.set_credentials(creds, project_id)

    mock_close_session.assert_called_once()
    self.assertEqual(bpd.options.bigquery.project, 'some-project-id')
    self.assertEqual(bpd.options.bigquery.credentials, creds)

    bigquery.validate(_QUERY)

    self.mock_read_gbq_colab.assert_called_once_with(
        _QUERY, dry_run=True, pyformat_args={}
    )

    # Second call should reuse the global session.
    bigquery.validate(_QUERY)

    mock_close_session.assert_called_once()
    self.assertEqual(self.mock_read_gbq_colab.call_count, 2)

  def test_validate_sql_with_validation_errors(self):
    error_message = 'Unknown table: `bigquery-public-data.samples.shakespeare`'
    self.mock_read_gbq_colab.side_effect = QueryJobError(
        'Something went wrong',
        [
            {
                'message': error_message,
            },
            {
                'message': 'Another error at [7:11]',
            },
        ],
    )
    expected = bigquery.ValidationFailure(
        errors=[
            bigquery.ValidationError(
                message=error_message, line=None, column=None
            ),
            bigquery.ValidationError(
                message='Another error at [7:11]', line=7, column=11
            ),
        ],
        authorization_failed=False,
    )

    result = bigquery.validate(_QUERY)

    self.assertEqual(expected, result)

  def test_validate_sql_extracts_line_and_column(self):
    self.mock_read_gbq_colab.side_effect = QueryJobError(
        'Something went wrong',
        [
            {
                'message': 'Syntax error at [1:1]',
            },
            {
                'message': 'A different error at [657:234]. Please fix',
            },
            {
                'message': '[123:] is incomplete',
            },
            {
                'message': 'This is a syntax error at [:123]',
            },
            {
                'message': '[0:0]',
            },
        ],
    )
    expected = bigquery.ValidationFailure(
        errors=[
            bigquery.ValidationError(
                message='Syntax error at [1:1]', line=1, column=1
            ),
            bigquery.ValidationError(
                message='A different error at [657:234]. Please fix',
                line=657,
                column=234,
            ),
            bigquery.ValidationError(
                message='[123:] is incomplete', line=None, column=None
            ),
            bigquery.ValidationError(
                message='This is a syntax error at [:123]',
                line=None,
                column=None,
            ),
            bigquery.ValidationError(message='[0:0]', line=0, column=0),
        ],
        authorization_failed=False,
    )

    result = bigquery.validate(_QUERY)

    self.assertEqual(expected, result)

  def test_validate_sql_with_auth_error(self):
    error_message = 'Your default credentials were not found'
    self.mock_read_gbq_colab.side_effect = (
        auth_exceptions.DefaultCredentialsError(error_message)
    )
    expected = bigquery.ValidationFailure(
        errors=[
            bigquery.ValidationError(
                message=error_message, line=None, column=None
            )
        ],
        authorization_failed=True,
    )

    result = bigquery.validate(_QUERY)

    self.assertEqual(expected, result)

  def test_validate_sql_with_no_error_messages(self):
    error_message = 'Unexpected error'
    self.mock_read_gbq_colab.side_effect = QueryJobError(error_message, [])
    expected = bigquery.ValidationFailure(
        errors=[
            bigquery.ValidationError(
                message=error_message, line=None, column=None
            )
        ],
        authorization_failed=False,
    )

    result = bigquery.validate(_QUERY)

    self.assertEqual(expected, result)

  def test_validate_sql_with_unknown_exception(self):
    error_message = 'Unexpected error'
    self.mock_read_gbq_colab.side_effect = Exception(error_message)
    expected = bigquery.ValidationFailure(
        errors=[
            bigquery.ValidationError(
                message=error_message, line=None, column=None
            )
        ],
        authorization_failed=False,
    )

    result = bigquery.validate(_QUERY)

    self.assertEqual(expected, result)


class RunTest(unittest.TestCase):

  def setUp(self):
    super().setUp()
    bpd.options.bigquery.project = None
    bpd.options.bigquery.credentials = None
    bpd.options.display.repr_mode = 'head'
    self.mock_read_gbq_colab = self.enterContext(
        mock.patch.object(bpd, '_read_gbq_colab')
    )
    self.mock_bpd_option_context = self.enterContext(
        mock.patch.object(bpd, 'option_context', wraps=bpd.option_context)
    )

  def test_run(self):
    expected = mock.Mock(spec=bpd.DataFrame)
    self.mock_read_gbq_colab.return_value = expected

    self.assertEqual(bpd.options.display.repr_mode, 'head')

    self.assertEqual(bigquery.run(_QUERY), expected)

    self.mock_bpd_option_context.assert_called_once_with(
        'display.progress_bar', None
    )
    self.mock_read_gbq_colab.assert_called_once_with(_QUERY, pyformat_args={})
    self.assertEqual(bpd.options.display.repr_mode, 'anywidget')

  @mock.patch.object(IPython, 'get_ipython')
  def test_run_with_pyformat_args(self, mock_get_ipython):
    query = 'SELECT {",".join(columns)} FROM {table}'
    user_ns = {
        'columns': ['col1', 'col2', 'col3'],
        'table': 'bigquery-public-data.samples.shakespeare',
    }
    mock_get_ipython.return_value.user_ns = user_ns
    expected = mock.Mock(spec=bpd.DataFrame)
    self.mock_read_gbq_colab.return_value = expected

    self.assertEqual(bigquery.run(query), expected)

    self.mock_bpd_option_context.assert_called_once_with(
        'display.progress_bar', None
    )
    self.mock_read_gbq_colab.assert_called_once_with(
        query, pyformat_args=user_ns
    )

  @mock.patch.object(bpd, 'close_session')
  def test_set_credentials_configures_bigframes(self, mock_close_session):
    creds = credentials.AnonymousCredentials()
    project_id = 'some-project-id'

    self.assertIsNone(bpd.options.bigquery.project)
    self.assertIsNone(bpd.options.bigquery.credentials)

    bigquery.set_credentials(creds, project_id)

    mock_close_session.assert_called_once()
    self.assertEqual(bpd.options.bigquery.project, 'some-project-id')
    self.assertEqual(bpd.options.bigquery.credentials, creds)


if __name__ == '__main__':
  unittest.main()
