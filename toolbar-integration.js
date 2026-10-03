// toolbar_integration.js
/**
 * Integration with Colab toolbar for the Deploy to Cloud feature.
 */
goog.module('colab.deploy_to_cloud.toolbar');

const dom = goog.require('goog.dom');
const events = goog.require('goog.events');
const {getNotebookApp} = goog.require('colab.app');
const {createElement} = goog.require('colab.dom');
const {showDeployToCloudDialog} = goog.require('colab.deploy_to_cloud.dialog');

/**
 * Adds the Deploy to Cloud button to the Colab toolbar.
 */
function addToolbarButton() {
  // Check if user is authenticated with Google account
  getNotebookApp().kernel.invokeFunction('colab.deploy_to_cloud.check_auth', [])
      .then(result => {
        const isAuthenticated = result.data['application/json'];
        if (isAuthenticated) {
          insertToolbarButton_();
        }
      })
      .catch(error => {
        console.error('Failed to check authentication:', error);
      });
}

/**
 * Inserts the Deploy to Cloud button into the toolbar.
 * @private
 */
function insertToolbarButton_() {
  // Create deploy icon
  const iconSvg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" 
         stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"></path>
      <path d="M12 12v9"></path>
      <path d="m8 17 4 4 4-4"></path>
    </svg>
  `;
  
  // Create button element
  const buttonEl = createElement('button', {
    'class': 'toolbar-deploy-button',
    'title': 'Deploy to Google Cloud'
  });
  
  // Set button inner HTML
  buttonEl.innerHTML = iconSvg + 'Deploy to Cloud';
  
  // Add click event listener
  events.listen(buttonEl, 'click', () => {
    showDeployToCloudDialog(getNotebookApp().getActiveNotebook());
  });
  
  // Find toolbar element
  const toolbar = document.querySelector('.colab-toolbar');
  if (toolbar) {
    // Insert before overflow menu
    const overflowMenu = toolbar.querySelector('.overflow-menu-button');
    if (overflowMenu) {
      toolbar.insertBefore(buttonEl, overflowMenu);
    } else {
      toolbar.appendChild(buttonEl);
    }
  }
}

// Export functions
exports = {
  addToolbarButton,
};
