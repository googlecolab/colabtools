#
# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Helper to provide resources via the colab service worker.

Example inside Colab:

# First, create a resource in Python
  from google.colab import html
  ref = html.create_resource(content='hello world')

  # Next, execute javascript code that uses that resource
  from IPython.display import display, Javascript

  display(Javascript('''
  var content = {ref.content!r};
  var url = {ref.url!r};

  fetch(url)
    .then(r => r.text())
    .then(c => console.log("Content matches:", c === content))
  '''.format(ref=ref)))
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import abc
import collections
import mimetypes
import uuid
import weakref

import six
import tornado.web

from google.colab.html import _background_server


@six.add_metaclass(abc.ABCMeta)
class _Resource(object):
  """Abstract resource class to handle content to colab."""

  def __init__(self, provider, headers, extension, route):
    if not isinstance(headers, collections.Mapping):
      raise ValueError('headers must be a dict')
    if route and extension:
      raise ValueError('Should only provide one of route or extension.')
    self.headers = headers
    self._route = route
    if route:
      self._guid = route
    else:
      self._guid = str(uuid.uuid4())
      if extension:
        self._guid += '.' + extension
    self._provider = provider

  @abc.abstractmethod
  def get(self, handler):
    """Gets the resource using the tornado handler passed in.

    Args:
      handler: Tornado handler to be used.
    """
    for key, value in self.headers.items():
      handler.set_header(key, value)

  @property
  def guid(self):
    """Unique id used to serve and reference the resource."""
    return self._guid

  @property
  def url(self):
    """Url to fetch the resource at."""
    return 'https://localhost:{}/{}'.format(self._provider.port, self._guid)


class _ContentResource(_Resource):

  def __init__(self, content, *args, **kwargs):
    self.content = content
    super(_ContentResource, self).__init__(*args, **kwargs)

  def get(self, handler):
    super(_ContentResource, self).get(handler)
    handler.write(self.content)


class _FileResource(_Resource):
  """Handle file resources."""

  def __init__(self, filepath, *args, **kwargs):
    self.filepath = filepath
    super(_FileResource, self).__init__(*args, **kwargs)

  def get(self, handler):
    super(_FileResource, self).get(handler)
    with open(self.filepath) as f:
      data = f.read()
    handler.write(data)


class _HandlerResource(_Resource):

  def __init__(self, func, *args, **kwargs):
    self.func = func
    super(_HandlerResource, self).__init__(*args, **kwargs)

  def get(self, handler):
    super(_HandlerResource, self).get(handler)
    content = self.func()
    handler.write(content)


class _ResourceHandler(tornado.web.RequestHandler):
  """Serves the `Resource` objects."""

  def initialize(self, resources):
    self._resources = resources

  def get(self):
    path = self.request.path
    resource = self._resources.get(path.lstrip('/'))
    if not resource:
      raise tornado.web.HTTPError(404, 'Resource at %s not found', path)

    content_type, _ = mimetypes.guess_type(path)
    if content_type:
      self.set_header('Content-Type', content_type)
    resource.get(self)


class _Provider(_background_server._BackgroundServer):  # pylint: disable=protected-access
  """Background server which can provide a set of resources."""

  def __init__(self):
    """Initialize the server with a ResourceHandler script."""
    resources = weakref.WeakValueDictionary()
    self._resources = resources

    app = tornado.web.Application([
        (r'.*', _ResourceHandler, dict(resources=self._resources)),
    ])

    super(_Provider, self).__init__(app)

  def create(self,
             content=None,
             filepath=None,
             handler=None,
             headers=None,
             extension=None,
             route=None):
    """Creates and provides a new resource to be served.

    Can only provide one of content, path, or handler.

    Args:
      content: The string or byte content to return.
      filepath: The filepath to a file whose contents should be returned.
      handler: A function which will be executed and returned on each request.
      headers: A dict of header values to return.
      extension: Optional extension to add to the url.
      route: Optional route to serve on.
    Returns:
      The `_Resource` object which will be served and will provide its url.
    Raises:
      ValueError: If you don't provide one of content, filepath, or handler.
    """
    sources = sum(map(bool, (content, filepath, handler)))
    if sources != 1:
      raise ValueError(
          'Must provide exactly one of content, filepath, or handler')

    if not headers:
      headers = {}

    if route:
      route = route.lstrip('/')

    if content:
      resource = _ContentResource(
          content,
          headers=headers,
          extension=extension,
          provider=self,
          route=route)
    elif filepath:
      resource = _FileResource(
          filepath,
          headers=headers,
          extension=extension,
          provider=self,
          route=route)
    elif handler:
      resource = _HandlerResource(
          handler,
          headers=headers,
          extension=extension,
          provider=self,
          route=route)
    else:
      raise ValueError('Must provide one of content, filepath, or handler.')

    self._resources[resource.guid] = resource
    if self._server_thread is None:
      self.start()
    return resource


# Global singleton instance
_global_provider = _Provider()

create = _global_provider.create
