# kernel_integration.py
"""
Module for integrating the Cloud Deploy feature with the Colab kernel.
"""
import json
from IPython.core.magic import register_line_magic
from google.colab import output
from google.colab.output import eval_js

from colabtools.deploy.cloud_deploy import CloudDeploymentManager


# Initialize the deployment manager
_deployment_manager = CloudDeploymentManager()


def _register_kernel_functions():
    """Register functions that can be called from JavaScript."""
    
    @register_line_magic
    def deploy_to_cloud(line):
        """Magic command to deploy the current notebook to Google Cloud."""
        from IPython import get_ipython
        
        notebook = get_ipython().kernel.shell.user_ns.get('_ih', [])
        service_name = line.strip() or f"colab-deploy-{int(time.time())}"
        
        # Open the deployment dialog
        eval_js("""
        (async function() {
            const {showDeployToCloudDialog} = await import('/nbextensions/colab/deploy_to_cloud/dialog.js');
            showDeployToCloudDialog(IPython.notebook);
        })();
        """)
    
    output.register_callback('colab.deploy_to_cloud.get_projects', 
                           _get_available_projects)
    output.register_callback('colab.deploy_to_cloud.get_regions', 
                           _get_available_regions)
    output.register_callback('colab.deploy_to_cloud.deploy', 
                           _deploy_to_cloud)


def _get_available_projects():
    """Get available Google Cloud projects for the current user."""
    try:
        projects = _deployment_manager.get_available_projects()
        return projects
    except Exception as e:
        raise RuntimeError(f"Failed to get projects: {str(e)}")


def _get_available_regions(project_id, service):
    """Get available regions for the specified service."""
    try:
        regions = _deployment_manager.get_available_regions(service)
        return regions
    except Exception as e:
        raise RuntimeError(f"Failed to get regions: {str(e)}")


def _deploy_to_cloud(notebook, project_id, service_type, service_name, region):
    """
    Deploy the notebook to Google Cloud.
    
    Args:
        notebook: The notebook content
        project_id: Google Cloud project ID
        service_type: Type of service (cloudrun, cloudfunctions)
        service_name: Name for the deployed service
        region: GCP region for deployment
        
    Returns:
        Dict with deployment details
    """
    try:
        # Prepare deployment files
        _deployment_manager.prepare_deployment_files(notebook, service_name)
        
        # Deploy based on service type
        if service_type == "cloudrun":
            result = _deployment_manager.deploy_to_cloud_run(
                project_id, service_name, region)
        elif service_type == "cloudfunctions":
            result = _deployment_manager.deploy_to_cloud_functions(
                project_id, service_name, region)
        else:
            raise ValueError(f"Unsupported service type: {service_type}")
        
        # Clean up temporary files
        _deployment_manager.cleanup()
        
        return result
    except Exception as e:
        # Clean up on error
        _deployment_manager.cleanup()
        raise RuntimeError(f"Deployment failed: {str(e)}")


# Register kernel functions when this module is imported
_register_kernel_functions()
