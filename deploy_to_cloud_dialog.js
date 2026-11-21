// deploy_to_cloud_dialog.js
/**
 * JavaScript implementation for the Deploy to Cloud dialog and UI components.
 */
goog.module('colab.deploy_to_cloud.dialog');

const {Deferred} = goog.require('goog.async.Deferred');
const dom = goog.require('goog.dom');
const events = goog.require('goog.events');
const {getNotebookApp} = goog.require('colab.app');
const {Dialog} = goog.require('colab.Dialog');
const {createElement} = goog.require('colab.dom');

/**
 * The Deploy to Cloud dialog that handles project configuration and deployment.
 */
class DeployToCloudDialog {
  /**
   * @param {!Object} notebook The current notebook object
   */
  constructor(notebook) {
    /** @private {!Object} */
    this.notebook_ = notebook;
    
    /** @private {!Dialog} */
    this.dialog_ = new Dialog();
    
    /** @private {?string} */
    this.selectedProject_ = null;
    
    /** @private {?string} */
    this.selectedRegion_ = null;
    
    /** @private {?string} */
    this.selectedService_ = 'cloudrun';
    
    /** @private {?string} */
    this.serviceName_ = null;
  }

  /**
   * Shows the deployment configuration dialog.
   * @return {!Promise} A promise that resolves when deployment completes
   */
  show() {
    const deferred = new Deferred();
    
    // Create dialog content
    const dialogContent = this.createDialogContent_();
    
    // Configure dialog
    this.dialog_.setContent(dialogContent);
    this.dialog_.setTitle('Deploy to Cloud');
    this.dialog_.setOkText('Deploy');
    this.dialog_.setOkCallback(() => {
      this.handleDeploy_().then(result => {
        deferred.callback(result);
      }).catch(error => {
        deferred.errback(error);
      });
      return false; // Prevent dialog from closing immediately
    });
    
    // Show dialog
    this.dialog_.show();
    
    // Load projects asynchronously
    this.loadProjects_();
    
    return deferred.promise;
  }
  
  /**
   * Creates the dialog content element.
   * @return {!Element} The dialog content element
   * @private
   */
  createDialogContent_() {
    const container = createElement('div', {'class': 'deploy-to-cloud-dialog'});
    
    // Project selection
    const projectSection = createElement('div', {'class': 'deploy-section'});
    projectSection.appendChild(createElement('h3', {}, 'Google Cloud Project'));
    
    const projectSelect = createElement('select', {
      'id': 'project-select',
      'class': 'deploy-select',
      'required': true,
      'disabled': true
    });
    projectSelect.appendChild(createElement('option', {
      'value': '',
      'selected': true,
      'disabled': true
    }, 'Loading projects...'));
    
    events.listen(projectSelect, 'change', (e) => {
      this.selectedProject_ = e.target.value;
      this.updateRegions_();
    });
    
    projectSection.appendChild(projectSelect);
    container.appendChild(projectSection);
    
    // Deployment service
    const serviceSection = createElement('div', {'class': 'deploy-section'});
    serviceSection.appendChild(createElement('h3', {}, 'Deployment Service'));
    
    const serviceSelect = createElement('select', {
      'id': 'service-select',
      'class': 'deploy-select'
    });
    
    const serviceOptions = [
      {'value': 'cloudrun', 'label': 'Cloud Run'},
      {'value': 'cloudfunctions', 'label': 'Cloud Functions'}
    ];
    
    serviceOptions.forEach(option => {
      const optionEl = createElement('option', {'value': option.value}, option.label);
      serviceSelect.appendChild(optionEl);
    });
    
    events.listen(serviceSelect, 'change', (e) => {
      this.selectedService_ = e.target.value;
      this.updateRegions_();
    });
    
    serviceSection.appendChild(serviceSelect);
    container.appendChild(serviceSection);
    
    // Region selection
    const regionSection = createElement('div', {'class': 'deploy-section'});
    regionSection.appendChild(createElement('h3', {}, 'Region'));
    
    const regionSelect = createElement('select', {
      'id': 'region-select',
      'class': 'deploy-select',
      'required': true,
      'disabled': true
    });
    regionSelect.appendChild(createElement('option', {
      'value': '',
      'selected': true,
      'disabled': true
    }, 'Select a project first'));
    
    events.listen(regionSelect, 'change', (e) => {
      this.selectedRegion_ = e.target.value;
    });
    
    regionSection.appendChild(regionSelect);
    container.appendChild(regionSection);
    
    // Service name
    const nameSection = createElement('div', {'class': 'deploy-section'});
    nameSection.appendChild(createElement('h3', {}, 'Service Name'));
    
    const defaultName = `colab-deploy-${Math.floor(Date.now() / 1000)}`;
    const nameInput = createElement('input', {
      'id': 'service-name',
      'class': 'deploy-input',
      'type': 'text',
      'value': defaultName,
      'required': true
    });
    
    events.listen(nameInput, 'input', (e) => {
      this.serviceName_ = e.target.value;
    });
    
    this.serviceName_ = defaultName;
    nameSection.appendChild(nameInput);
    container.appendChild(nameSection);
    
    // Status section for deployment progress
    const statusSection = createElement('div', {
      'id': 'deploy-status',
      'class': 'deploy-section deploy-status',
      'style': 'display: none;'
    });
    container.appendChild(statusSection);
    
    return container;
  }
  
  /**
   * Loads available Google Cloud projects for the user.
   * @private
   */
  loadProjects_() {
    const projectSelect = dom.getElement('project-select');
    
    // Make a request to the Python kernel to get available projects
    getNotebookApp().kernel.invokeFunction('colab.deploy_to_cloud.get_projects', [])
        .then(result => {
          const projects = result.data['application/json'];
          
          // Clear loading option
          projectSelect.innerHTML = '';
          
          // Add default option
          projectSelect.appendChild(createElement('option', {
            'value': '',
            'selected': true,
            'disabled': true
          }, 'Select a project'));
          
          // Add project options
          projects.forEach(project => {
            const option = createElement('option', {'value': project.projectId}, 
                `${project.name} (${project.projectId})`);
            projectSelect.appendChild(option);
          });
          
          // Enable select
          projectSelect.disabled = false;
        })
        .catch(error => {
          console.error('Failed to load projects:', error);
          projectSelect.innerHTML = '';
          projectSelect.appendChild(createElement('option', {
            'value': '',
            'selected': true,
            'disabled': true
          }, 'Failed to load projects'));
        });
  }
  
  /**
   * Updates available regions based on selected project and service.
   * @private
   */
  updateRegions_() {
    if (!this.selectedProject_ || !this.selectedService_) {
      return;
    }
    
    const regionSelect = dom.getElement('region-select');
    regionSelect.disabled = true;
    regionSelect.innerHTML = '';
    regionSelect.appendChild(createElement('option', {
      'value': '',
      'selected': true,
      'disabled': true
    }, 'Loading regions...'));
    
    // Make a request to the Python kernel to get available regions
    getNotebookApp().kernel.invokeFunction('colab.deploy_to_cloud.get_regions', 
        [this.selectedProject_, this.selectedService_])
        .then(result => {
          const regions = result.data['application/json'];
          
          // Clear loading option
          regionSelect.innerHTML = '';
          
          // Add default option
          regionSelect.appendChild(createElement('option', {
            'value': '',
            'selected': true,
            'disabled': true
          }, 'Select a region'));
          
          // Add region options
          regions.forEach(region => {
            const option = createElement('option', {'value': region}, region);
            regionSelect.appendChild(option);
          });
          
          // Enable select
          regionSelect.disabled = false;
        })
        .catch(error => {
          console.error('Failed to load regions:', error);
          regionSelect.innerHTML = '';
          regionSelect.appendChild(createElement('option', {
            'value': '',
            'selected': true,
            'disabled': true
          }, 'Failed to load regions'));
        });
  }
  
  /**
   * Handles the deployment process.
   * @return {!Promise} A promise that resolves when deployment completes
   * @private
   */
  handleDeploy_() {
    // Validate inputs
    if (!this.selectedProject_ || !this.selectedRegion_ || !this.serviceName_) {
      return Promise.reject(new Error('Please fill all required fields'));
    }
    
    // Update UI to show deployment in progress
    this.dialog_.setOkEnabled(false);
    this.dialog_.setCancelEnabled(false);
    
    const statusElement = dom.getElement('deploy-status');
    statusElement.style.display = 'block';
    statusElement.innerHTML = 'Deploying to Google Cloud...';
    
    // Make a request to the Python kernel to deploy
    return getNotebookApp().kernel.invokeFunction('colab.deploy_to_cloud.deploy', [
      this.notebook_,
      this.selectedProject_,
      this.selectedService_,
      this.serviceName_,
      this.selectedRegion_
    ])
    .then(result => {
      const deployResult = result.data['application/json'];
      
      // Update status with success message
      statusElement.innerHTML = `
        <div class="deploy-success">
          <h3>Deployment Successful!</h3>
          <p>Your service is now available at:</p>
          <a href="${deployResult.url}" target="_blank">${deployResult.url}</a>
        </div>
      `;
      
      // Enable close button
      this.dialog_.setOkText('Close');
      this.dialog_.setOkEnabled(true);
      this.dialog_.setOkCallback(() => {
        this.dialog_.dispose();
        return true;
      });
      
      return deployResult;
    })
    .catch(error => {
      console.error('Deployment failed:', error);
      
      // Update status with error message
      statusElement.innerHTML = `
        <div class="deploy-error">
          <h3>Deployment Failed</h3>
          <p>${error.message || 'An error occurred during deployment'}</p>
        </div>
      `;
      
      // Enable close button
      this.dialog_.setCancelEnabled(true);
      this.dialog_.setOkText('Try Again');
      this.dialog_.setOkEnabled(true);
      
      throw error;
    });
  }
}

/**
 * Creates and shows the Deploy to Cloud dialog.
 * @param {!Object} notebook The current notebook object
 * @return {!Promise} A promise that resolves when deployment completes
 */
function showDeployToCloudDialog(notebook) {
  const dialog = new DeployToCloudDialog(notebook);
  return dialog.show();
}

exports = {
  showDeployToCloudDialog,
};
