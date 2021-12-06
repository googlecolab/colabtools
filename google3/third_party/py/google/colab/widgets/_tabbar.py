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
# See the License for the specific language governing permissions and
# limitations under the License.
"""Provides a tabbar widget that redirects output into separate tabs."""
import contextlib

from google.colab.output import _js_builder as js
from google.colab.output import _publish
from google.colab.widgets import _widget
import six


class TabBar(_widget.OutputAreaWidget):
  """UI Widget to generate tab bars in the output.

  Sample usage:
     tab = TabBar(['evening', 'morning'])
     with tab.output_to('evening'):
       print('hi')

     with tab.output_to('morning'):
       print('bye')
  """
  TABBAR_JS = '/nbextensions/google.colab/tabbar_main.min.js'
  TAB_CSS = '/nbextensions/google.colab/tabbar.css'

  def __init__(self, tab_names, location='top'):
    """Constructor.

    Args:
      tab_names: list of strings for the tab names.

      location: location of tabs.
      Acceptable values:
         'top',
         'start' (left of the text, for left-to-right text)
         'end' (right of the text for left-to-right text)
         'bottom'
    Raises:
      ValueError: if location is not valid
    """
    if location not in ('top', 'bottom', 'start', 'end'):
      raise ValueError('Invalid value for location: {!r}'.format(location))
    self.tab_names = tab_names
    self._location = location
    self._active = 0
    super(TabBar, self).__init__()

  def _tab_id(self, index):
    return '%s_%d' % (self._content_div, index)

  def _html_repr(self):
    """Generates html representation for this tab.

    Returns:
      string - the html representation
    """
    return """<div id="%(id)s"></div>""" % {
        'id': self._id,
    }

  def _get_tab_id(self, index_or_name):
    if isinstance(index_or_name, six.string_types):
      names = tuple(self.tab_names)
      index = names.index(index_or_name)
      if index_or_name in names[index + 1:]:
        raise ValueError('Ambiguous tab name: %s ' % index_or_name)
    else:
      index = index_or_name
    tabid = self._tab_id(index)
    return tabid, index

  def _prepare_component_for_output(self, index, select):
    if select:
      js.js_global[self._id].setSelectedTabIndex(index)

  @contextlib.contextmanager
  def output_to(self, tab, select=True):
    """Sets current output tab.

    Args:
      tab: the tab's name matching one of the tab_names provided in the
        constructor. Alternatively a 0-based index can be used. Note: if
        tab_names contains duplicates, they can only be accessed via index.
        Trying to access by name will trigger ValueError
      select: if True this will also select the tab, otherwise the tab will be
        updated in the background

    Yields:
      None (once tab is selected)
    """
    if not self._published:
      self._publish()
    tabid, index = self._get_tab_id(tab)
    with self._active_component(
        tabid, init_params={
            'select': select,
            'index': index
        }):
      yield

  def clear_tab(self, tab=None):
    """Clears tabs.

    Args:
      tab: if None clears current tab  otherwise clears the corresponding tab.
      Tab could be the tab's name (if it is unique), or 0-based index.
    """
    if tab is not None:
      tabid, _ = self._get_tab_id(tab)
    else:
      tabid = None
    self._clear_component(tabid)

  def __iter__(self):
    """Iterates over tabs. Allows quick population of tab in a loop.

    Yields:
      current tab index
    """
    self._publish()
    for i, _ in enumerate(self.tab_names):
      with self.output_to(i):
        yield i

  def _publish(self):
    """Publishes this tab bar in the given cell.

    Note: this function is idempotent.
    """
    if self._published:
      return
    content_height = 'initial',
    content_border = '0px',
    border_color = '#a7a7a7',
    self._content_div = self._id + '_content'
    super(TabBar, self)._publish()
    with self._output_in_widget():
      _publish.css(url=self.TAB_CSS)
      _publish.javascript(url=self.TABBAR_JS)
      _publish.html(self._html_repr())

      js.js_global.colab_lib.createTabBar({
          'location': self._location,
          'elementId': self._id,
          'tabNames': self.tab_names,
          'initialSelection': self._active,
          'contentBorder': content_border,
          'contentHeight': content_height,
          'borderColor': border_color,
      })
      # Note: publish() will only be called once, thus this will never change
      # already visible tab.
      js.js_global[self._id].setSelectedTabIndex(0)
