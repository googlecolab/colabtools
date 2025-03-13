# cloud_deploy.py
"""
Module for handling Colab notebook deployment to Google Cloud.
"""
import os
import json
import subprocess
import tempfile
from typing import Dict, List, Optional, Tuple

from google.auth import exceptions as auth_exceptions
from google.cloud import storage, build
from google.colab import auth
from colabtools.export import export_notebook_as_script


class CloudDeploymentManager:
    """Manages the deployment of Colab notebooks to Google Cloud services."""
    
    SUPPORTED_SERVICES = ["cloudrun", "cloudfunctions"]
    DEFAULT_REGION = "us-central1"
    
    def __init__(self):
        self.authenticated = False
        self.project_id = None
        self.temp_dir = None
    
    def authenticate(self) -> bool:
        """Authenticate the user with Google Cloud."""
        try:
            auth.authenticate_user(clear_output=True)
            self.authenticated = True
            return True
        except auth_exceptions.GoogleAuthError:
            return False
    
    def get_available_projects(self) -> List[Dict]:
        """Get list of available GCP projects for the authenticated user."""
        if not self.authenticated:
            self.authenticate()
            
        result = subprocess.run(
            ["gcloud", "projects", "list", "--format=json"],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    
    def get_available_regions(self, service: str) -> List[str]:
        """Get available regions for the specified service."""
        if service == "cloudrun":
            result = subprocess.run(
                ["gcloud", "run", "regions", "list", "--format=json"],
                capture_output=True,
                text=True,
                check=True
            )
            regions_data = json.loads(result.stdout)
            return [region["name"] for region in regions_data]
        elif service == "cloudfunctions":
            result = subprocess.run(
                ["gcloud", "functions", "regions", "list", "--format=json"],
                capture_output=True,
                text=True,
                check=True
            )
            regions_data = json.loads(result.stdout)
            return [region["name"] for region in regions_data]
        return []
    
    def prepare_deployment_files(self, notebook, service_name: str) -> str:
        """
        Convert notebook to Python script and create necessary deployment files.
        
        Args:
            notebook: The Colab notebook object
            service_name: Name for the deployed service
            
        Returns:
            Path to the temporary directory containing deployment files
        """
        # Create temporary directory for deployment files
        self.temp_dir = tempfile.mkdtemp()
        
        # Export notebook to Python script
        script_content = export_notebook_as_script(notebook)
        script_path = os.path.join(self.temp_dir, "main.py")
        with open(script_path, "w") as f:
            f.write(script_content)
        
        # Extract and create requirements.txt
        requirements = self._extract_requirements(notebook)
        req_path = os.path.join(self.temp_dir, "requirements.txt")
        with open(req_path, "w") as f:
            f.write("\n".join(requirements))
        
        # Create Dockerfile
        dockerfile_path = os.path.join(self.temp_dir, "Dockerfile")
        with open(dockerfile_path, "w") as f:
            f.write(self._generate_dockerfile(service_name))
        
        return self.temp_dir
    
    def _extract_requirements(self, notebook) -> List[str]:
        """Extract required packages from notebook imports."""
        # This is a simplified implementation
        # A more robust implementation would parse the notebook cells and extract imports
        standard_libs = ["os", "sys", "json", "time", "math", "random", "datetime", "collections"]
        common_deps = ["numpy", "pandas", "matplotlib", "seaborn", "scikit-learn", "tensorflow", "torch", "transformers"]
        
        # Add basic dependencies that are likely needed
        return common_deps + ["google-cloud-storage", "flask", "gunicorn"]
    
    def _generate_dockerfile(self, service_name: str) -> str:
        """Generate a Dockerfile for the service."""
        return """FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT 8080
EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]
"""
    
    def deploy_to_cloud_run(self, project_id: str, service_name: str, region: str) -> Dict:
        """
        Deploy the application to Cloud Run.
        
        Args:
            project_id: Google Cloud project ID
            service_name: Name for the Cloud Run service
            region: GCP region for deployment
            
        Returns:
            Dict with deployment details including service URL
        """
        self.project_id = project_id
        
        # Build and push container image
        image_url = f"gcr.io/{project_id}/{service_name}"
        
        print(f"Building and pushing container image to {image_url}...")
        subprocess.run(
            ["gcloud", "builds", "submit", "--tag", image_url, self.temp_dir],
            check=True
        )
        
        # Deploy to Cloud Run
        print(f"Deploying to Cloud Run in {region}...")
        result = subprocess.run(
            [
                "gcloud", "run", "deploy", service_name,
                "--image", image_url,
                "--region", region,
                "--platform", "managed",
                "--allow-unauthenticated",
                "--format=json"
            ],
            capture_output=True,
            text=True,
            check=True
        )
        
        deployment_result = json.loads(result.stdout)
        return {
            "service_name": service_name,
            "status": "deployed",
            "url": deployment_result.get("status", {}).get("url", ""),
            "region": region,
            "project": project_id
        }
    
    def deploy_to_cloud_functions(self, project_id: str, function_name: str, region: str) -> Dict:
        """
        Deploy the application to Cloud Functions.
        
        Args:
            project_id: Google Cloud project ID
            function_name: Name for the Cloud Function
            region: GCP region for deployment
            
        Returns:
            Dict with deployment details including function URL
        """
        self.project_id = project_id
        
        # Deploy to Cloud Functions
        print(f"Deploying to Cloud Functions in {region}...")
        result = subprocess.run(
            [
                "gcloud", "functions", "deploy", function_name,
                "--runtime", "python39",
                "--trigger-http",
                "--allow-unauthenticated",
                "--region", region,
                "--source", self.temp_dir,
                "--entry-point", "app",
                "--format=json"
            ],
            capture_output=True,
            text=True,
            check=True
        )
        
        deployment_result = json.loads(result.stdout)
        return {
            "function_name": function_name,
            "status": "deployed",
            "url": deployment_result.get("httpsTrigger", {}).get("url", ""),
            "region": region,
            "project": project_id
        }
    
    def cleanup(self):
        """Clean up temporary files."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)
            self.temp_dir = None
