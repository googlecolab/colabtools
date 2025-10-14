import unittest
from unittest import mock

from google.colab import auth


class AuthTest(unittest.TestCase):

  @mock.patch('google_auth_oauthlib.flow.InstalledAppFlow')
  def test_authenticate_desktop_application(self, mock_flow):
    """Test that authenticate_desktop_application calls run_console."""
    mock_flow.from_client_secrets_file.return_value = mock_flow
    auth.authenticate_desktop_application(
        'tests/client_secrets.json', ['scope1', 'scope2']
    )
    mock_flow.from_client_secrets_file.assert_called_once_with(
        'tests/client_secrets.json', ['scope1', 'scope2']
    )
    mock_flow.run_console.assert_called_once()


if __name__ == '__main__':
  unittest.main()
