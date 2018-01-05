# Copyright 2017 Google Inc.
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
# See the License for the specific language govestylerning permissions and
# limitations under the License.
"""Base widget for interactive elements."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import contextlib

from google.colab import errors
from google.colab import output
from google.colab.output import _tags
from google.colab.output import _util

# pylint: disable=invalid-name
WidgetException = errors.WidgetException


class OutputAreaWidget(object):
  """Base widget that redirects output into UI elements, e.g. table."""

  def __init__(self):
    self._published = False
    self._id = _util.get_locally_unique_id()
    self._saved_output_area = 'output_area_' + self._id
    self._tag = 'outputarea_' + self._id
    self._publish()

  def _publish(self):
    """Publishes this widget.

    Default does nothing but saves the current output area.
    """
    _util.flush_all()
    self._published = True
    # We save active output tags, and use that for all output inside any of the
    # subcomponents, even if they are no longer active.
    # This is done so that if the table # is deleted via tags that are
    # currently active, all its content
    # is also cleaned up.
    self._saved_output_tags = _tags.get_active_tags()
    self._current_component = None
    self.output_tags = self._saved_output_tags.union([self._tag])

  def remove(self, wait=False):
    """Removes the widget from the document.

    Args:
      wait: if true the actual deletion doesn't happen until the next output.
    """
    _util.flush_all()
    _tags.clear(wait, self.output_tags)

  @contextlib.contextmanager
  def _active_component(self, component_id):
    """Sets active subcomponent."""
    if not self._published:
      self._publish()
    if self._current_component is not None:
      raise WidgetException('Already inside a component')
    self._current_component = component_id
    _util.flush_all()
    with self._output_in_widget():
      with output.use_tags(self._current_component):
        with output.redirect_to_element('#' + component_id):
          with output.use_tags('user_output'):
            try:
              yield
            finally:
              _util.flush_all()
              self._current_component = None

  @contextlib.contextmanager
  def _output_in_widget(self):
    with output.use_tags(self.output_tags):
      try:
        yield
      finally:
        _util.flush_all()

  def _clear_component(self, component_id=None, wait=False):
    """Clears currently active component.

    Args:
      component_id: which component to clear.
      wait: if True, the output won't be cleared until the next user output.
      See colab.output.clear for full details.

    Raises:
      WidgetException: if component_id and no active element is
      selected
    """
    _util.flush_all()
    if component_id is None:
      if self._current_component is None:
        raise WidgetException('No active component selected')
      component_id = self._current_component
    if component_id == self._current_component:
      # Do not clear the part that sets current active element.
      # If we did, this would have made all consecutive output to stream
      # to wrong outputarea on reload.
      output.clear(wait, output_tags=[component_id] + ['user_output'])
    else:
      output.clear(wait, output_tags=[component_id])
