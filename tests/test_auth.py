import unittest
from unittest import mock

from google.colab import auth

class AuthTest(unittest.TestCase):

  @mock.patch('subprocess.Popen')
  @mock.patch('builtins.input')
  @mock.patch('os.fsync')
  @mock.patch('tempfile.mkstemp')
  def test_gcloud_login_with_calendar_scope(self, mock_mkstemp, mock_fsync, mock_input, mock_popen):
    mock_mkstemp.return_value = (None, 'tmpfile')
    mock_popen.return_value.communicate.return_value = ('', '')
    mock_popen.return_value.returncode = 0
    auth._gcloud_login()
    mock_popen.assert_called_once()
    gcloud_command = mock_popen.call_args[0][0]
    self.assertIn(
        '--scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/calendar.readonly',
        gcloud_command)

if __name__ == '__main__':
  unittest.main()
