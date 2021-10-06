# Copyright 2021 Google Inc.
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
"""Support for custom Jupyter Widgets in Colab."""

import IPython as _IPython

_supported_widgets_versions = {
    '5.0.0a': 'e680a8b83b2ea152',
}
_default_version = '5.0.0a'
_installed_url = None


def enable_custom_widget_manager(version=_default_version):
  """Enables a Jupyter widget manager which supports custom widgets.

  This will enable loading the required code from third party websites.

  Args:
     version: The version of Jupyter widgets for which support will be enabled.
  """

  version_hash = _supported_widgets_versions.get(version)
  if not version_hash:
    raise ValueError(
        'Unknown widgets version: {version}'.format(version=version))
  _install_custom_widget_manager(
      'https://ssl.gstatic.com/colaboratory-static/widgets/colab-cdn-widget-manager/{version_hash}/manager.min.js'
      .format(version_hash=version_hash))


def disable_custom_widget_manager():
  """Disable support for custom Jupyter widgets."""

  _install_custom_widget_manager(None)


def _install_custom_widget_manager(url):
  """Install a custom Jupyter widget manager.

  Args:
    url: The URL to an ES6 module which implements the custom widget manager
      interface or None to disable third-party widget support.
  """

  global _installed_url
  if url and not _installed_url:
    _IPython.get_ipython().display_pub.register_hook(_widget_display_hook)
  elif not url and _installed_url:
    _IPython.get_ipython().display_pub.unregister_hook(_widget_display_hook)

  _installed_url = url


_WIDGET_MIME_TYPE = 'application/vnd.jupyter.widget-view+json'


def _widget_display_hook(msg):
  """Display hook to enable custom widget manager info in the display item."""
  if not _installed_url:
    return msg
  content = msg.get('content', {})
  if not content:
    return msg
  widget_data = content.get('data', {}).get(_WIDGET_MIME_TYPE)
  if not widget_data:
    return msg

  widget_metadata = content.setdefault('metadata',
                                       {}).setdefault(_WIDGET_MIME_TYPE, {})
  widget_metadata['colab'] = {'custom_widget_manager': {'url': _installed_url,}}

  return msg
