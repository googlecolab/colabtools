# test_cloud_deploy.py
"""
Unit tests for the Cloud Deploy feature.
"""
import unittest
import os
import tempfile
from unittest import mock

import nbformat

from colabtools.deploy.cloud_deploy import CloudDeploymentManager


class TestCloudDeploymentManager(unittest.TestCase):
    """Tests for the CloudDeploymentManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.manager = CloudDeploymentManager()
        self.test_notebook = nbformat.v4.new_notebook()
        
        # Add a code cell to the notebook
        code_cell = nbformat.v4.new_code_cell(
            source='import numpy as np\nimport pandas as pd\n\nprint("Hello, world!")'
        )
        self.test_notebook.cells.append(code_cell)
        
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        if hasattr(self, 'test_dir') and os.path.exists(self.test_dir):
            import shutil
            shutil.rmtree(self.test_dir)
    
    @mock.patch('subprocess.run')
    def test_get_available_projects(self, mock_run):
        """Test getting available GCP projects."""
        # Mock subprocess.run to return a JSON list of projects
        mock_process = mock.Mock()
        mock_process.stdout = '[{"projectId": "test-project", "name": "Test Project"}]'
        mock_run.return_value = mock_process
        
        # Call the method
        result = self.manager.get_available_projects()
        
        # Check the result
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['projectId'], 'test-project')
        self.assertEqual(result[0]['name'], 'Test Project')
        
        # Verify subprocess.run was called correctly
        mock_run.assert_called_once_with(
            ['gcloud', 'projects', 'list', '--format=json'],
            capture_output=True,
            text=True,
            check=True
        )
    
    @mock.patch('subprocess.run')
    def test_get_available_regions_cloud_run(self, mock_run):
        """Test getting available regions for Cloud Run."""
        # Mock subprocess.run to return a JSON list of regions
        mock_process = mock.Mock()
        mock_process.stdout = '[{"name": "us-central1"}, {"name": "us-east1"}]'
        mock_run.return_value = mock_process
        
        # Call the method
        result = self.manager.get_available_regions('cloudrun')
        
        # Check the result
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], 'us-central1')
        self.assertEqual(result[1], 'us-east1')
        
        # Verify subprocess.run was called correctly
        mock_run.assert_called_once_with(
            ['gcloud', 'run', 'regions', 'list', '--format=json'],
            capture_output=True,
            text=True,
            check=True
        )
    
    @mock.patch('colabtools.export.export_notebook_as_script')
    def test_prepare_deployment_files(self, mock_export):
        """Test preparing deployment files."""
        # Mock export_notebook_as_script to return a Python script
        mock_export.return_value = 'print("Hello, world!")'
        
        # Call the method
        result_path = self.manager.prepare_deployment_files(self.test_notebook, 'test-service')
        
        # Check that the result is a directory
        self.assertTrue(os.path.isdir(result_path))
        
        # Check that the expected files were created
        self.assertTrue(os.path.exists(os.path.join(result_path, 'main.py')))
        self.assertTrue(os.path.exists(os.path.join(result_path, 'requirements.txt')))
        self.assertTrue(os.path.exists(os.path.join(result_path, 'Dockerfile')))
        
        # Verify export_notebook_as_script was called
        mock_export.assert_called_once_with(self.test_notebook)
    
    @mock.patch('subprocess.run')
    def test_deploy_to_cloud_run(self, mock_run):
        """Test deploying to Cloud Run."""
        # Set up mock for subprocess.run
        mock_process = mock.Mock()
        mock_process.stdout = '{"status": {"url": "https://test-service-xyz.run.app"}}'
        mock_run.return_value = mock_process
        
        # Set up the temp directory
        self.manager.temp_dir = self.test_dir
        
        # Call the method
        result = self.manager.deploy_to_cloud_run('test-project', 'test-service', 'us-central1')
        
        # Check the result
        self.assertEqual(result['service_name'], 'test-service')
        self.assertEqual(result['status'], 'deployed')
        self.assertEqual(result['url'], 'https://test-service-xyz.run.app')
        self.assertEqual(result['region'], 'us-central1')
        self.assertEqual(result['project'], 'test-project')
        
        # Verify subprocess.run was called
        self.assertEqual(mock_run.call_count, 2)  # build and deploy calls
    
    @mock.patch('subprocess.run')
    def test_deploy_to_cloud_functions(self, mock_run):
        """Test deploying to Cloud Functions."""
        # Set up mock for subprocess.run
        mock_process = mock.Mock()
        mock_process.stdout = '{"httpsTrigger": {"url": "https://us-central1-test-project.cloudfunctions.net/test-function"}}'
        mock_run.return_value = mock_process
        
        # Set up the temp directory
        self.manager.temp_dir = self.test_dir
        
        # Call the method
        result = self.manager.deploy_to_cloud_functions('test-project', 'test-function', 'us-central1')
        
        # Check the result
        self.assertEqual(result['function_name'], 'test-function')
        self.assertEqual(result['status'], 'deployed')
        self.assertEqual(result['url'], 'https://us-central1-test-project.cloudfunctions.net/test-function')
        self.assertEqual(result['region'], 'us-central1')
        self.assertEqual(result['project'], 'test-project')
        
        # Verify subprocess.run was called
        mock_run.assert_called_once()
    
    def test_cleanup(self):
        """Test cleaning up temporary files."""
        # Set the temp directory
        self.manager.temp_dir = self.test_dir
        
        # Call the cleanup method
        self.manager.cleanup()
        
        # Check that the directory no longer exists
        self.assertFalse(os.path.exists(self.test_dir))
        self.assertIsNone(self.manager.temp_dir)


class TestKernelIntegration(unittest.TestCase):
    """Tests for the kernel integration functions."""
    
    @mock.patch('colabtools.deploy.cloud_deploy.CloudDeploymentManager.get_available_projects')
    def test_get_available_projects(self, mock_get_projects):
        """Test getting available projects through kernel function."""
        from colabtools.deploy.kernel_integration import _get_available_projects
        
        # Mock the underlying method
        mock_get_projects.return_value = [{'projectId': 'test-project', 'name': 'Test Project'}]
        
        # Call the kernel function
        result = _get_available_projects()
        
        # Check the result
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['projectId'], 'test-project')
        
        # Verify the underlying method was called
        mock_get_projects.assert_called_once()
    
    @mock.patch('colabtools.deploy.cloud_deploy.CloudDeploymentManager.deploy_to_cloud_run')
    @mock.patch('colabtools.deploy.cloud_deploy.CloudDeploymentManager.prepare_deployment_files')
    def test_deploy_to_cloud(self, mock_prepare, mock_deploy):
        """Test deploying through kernel function."""
        from colabtools.deploy.kernel_integration import _deploy_to_cloud
        
        # Mock the underlying methods
        mock_prepare.return_value = '/tmp/test-dir'
        mock_deploy.return_value = {
            'service_name': 'test-service',
            'status': 'deployed',
            'url': 'https://test-service.run.app',
            'region': 'us-central1',
            'project': 'test-project'
        }
        
        # Create a test notebook
        notebook = nbformat.v4.new_notebook()
        
        # Call the kernel function
        result = _deploy_to_cloud(notebook, 'test-project', 'cloudrun', 'test-service', 'us-central1')
        
        # Check the result
        self.assertEqual(result['service_name'], 'test-service')
        self.assertEqual(result['status'], 'deployed')
        
        # Verify the underlying methods were called
        mock_prepare.assert_called_once_with(notebook, 'test-service')
        mock_deploy.assert_called_once_with('test-project', 'test-service', 'us-central1')


if __name__ == '__main__':
    unittest.main()
