#!/usr/bin/python
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
"""HTML renderable element in notebooks."""

import base64
import json
import string
import uuid
import IPython

import six

from google.colab import output
from google.colab.html import _provide
from google.colab.html import _resources

_MSG_CHUNK_SIZE = 1 * 1024 * 1024


def _to_html_str(obj):
  """Renders an object as html string on a best effort basis.

  IPython allows for registering of formatters. This
  tries to format the object using that registered text/html
  formater method. If it cannot and it is a string it returns
  it unchanged, otherwise it tries to serialize to json.
  The result should be something that can be html output
  for the notebook outputcell.

  Args:
    obj: An object to try to convert into HTML.
  Returns:
    An html string representation of the object.
  """
  ip = IPython.get_ipython()
  formatter = ip.display_formatter.formatters['text/html']
  try:
    render = formatter.lookup(obj)
    return render(obj)
  except KeyError:  # No html formatter exists
    pass
  if hasattr(obj, '_repr_html_'):
    html = obj._repr_html_()  # pylint: disable=protected-access
    if html:
      return html
  elif isinstance(obj, six.string_types):
    return obj
  else:
    try:
      return json.dumps(obj)
    except TypeError:  # Not json serializable
      pass
  return str(obj)


def _call_js_function(js_function, *args):
  """Evaluates a javascript string with arguments and returns its value."""
  serialized = json.dumps(args)
  if len(serialized) < _MSG_CHUNK_SIZE:
    return output.eval_js('({})(...{})'.format(js_function, serialized))

  name = str(uuid.uuid4())
  for i in range(0, len(serialized), _MSG_CHUNK_SIZE):
    chunk = serialized[i:i + _MSG_CHUNK_SIZE]
    output.eval_js(
        """window["{name}"] = (window["{name}"] || "") + atob("{b64_chunk}");
    """.format(
        name=name, b64_chunk=base64.b64encode(chunk.encode()).decode('ascii')),
        ignore_result=True)
  return output.eval_js("""
    (function() {{
      const msg = JSON.parse(window["{name}"]);
      delete window["{name}"];
      return ({js_function})(...msg);
    }})();
  """.format(name=name, js_function=js_function))


def _proxy(guid, msg):
  """Makes a proxy call on an element."""
  template = _resources.get_data(__name__, 'js/_proxy.js')
  if six.PY3:
    # pkgutil.get_data returns bytes, but we want a str.
    template = template.decode('utf8')
  return _call_js_function(template, guid, msg)


def _exists(guid):
  """Checks if an element with the given guid exists."""
  template = _resources.get_data(__name__, 'js/_proxy.js')
  if six.PY3:
    # pkgutil.get_data returns bytes, but we want a str.
    template = template.decode('utf8')
  return _call_js_function(template, guid, {'method': 'exists'}, False)


_utils_ref = None


def _utils_url():
  """Return the url to the utils script."""
  global _utils_ref
  if not _utils_ref:
    src = _resources.get_data(__name__, 'js/_html.js')
    if six.PY3:
      # pkgutil.get_data returns bytes, but we want a str.
      src = src.decode('utf8')
    _utils_ref = _provide.create(content=src, extension='js')
  return _utils_ref.url


_element_template = string.Template("""
$deps
<$tag id="$guid">
  $children
</$tag>
<script>
  (function() {
    async function init() {
      const name = '_google_colab_output_html';
      let script = document.getElementById(name);
      if (!script) {
        script = document.createElement('script');
        script.id = name;
        script._is_loaded = new Promise((resolve, reject) => {
          script.onload = resolve;
          script.onerror = reject;
        });
        script.src = '$utils';
        document.body.appendChild(script);
      }
      await script._is_loaded;
      await window.google.colab.html._createElement($config);
    }
    window.google.colab.output.pauseOutputUntil(init());
  })();
</script>
""")


class Element(object):
  """Create an object which will render as an html element in output cell."""

  def __init__(self, tag, attributes=None, properties=None, src=None):
    """Initialize the element.

    Args:
      tag: Custom element tag name.
      attributes: Initial attributes to set.
      properties: Initial properties to set.
      src: Entry point url of source for element. Should be a dict
        containing one of the following keys script, html, module.
        For example: {"script": "data:application/javascript;,"}
    Raises:
      ValueError: If invalid deps, attributes, or properites.
    """
    if src:
      if not ('script' in src or 'module' in src or 'html' in src):
        raise ValueError('Must provide a valid src.')
    self._src = src
    if attributes and not isinstance(attributes, dict):
      raise ValueError('attributes must be a dict.')
    if properties and not isinstance(properties, dict):
      raise ValueError('properties must be a dict.')
    self._tag = tag
    self._guid = str(uuid.uuid4())
    self._attributes = attributes or {}
    self._properties = properties or {}
    self._children = []
    self._js_listeners = {}
    self._py_listeners = {}
    self._parent = None
    self._could_exist = False

  def _exists(self):
    if not self._could_exist:
      return False
    return _exists(self._guid)

  def get_attribute(self, name):
    if not self._exists():
      return self._attributes.get(name)
    return _proxy(self._guid, {'method': 'getAttribute', 'name': name})

  def set_attribute(self, name, value):
    if not isinstance(value, six.string_types):
      raise ValueError('Attribute value must be a string')
    if not self._exists():
      self._attributes[name] = value
    else:
      _proxy(self._guid, {
          'method': 'setAttribute',
          'value': value,
          'name': name
      })

  def get_property(self, name):
    if not self._exists():
      return self._properties.get(name)
    return _proxy(self._guid, {'method': 'getProperty', 'name': name})

  def set_property(self, name, value):
    if not self._exists():
      self._properties[name] = value
    else:
      _proxy(self._guid, {
          'method': 'setProperty',
          'value': value,
          'name': name
      })

  def call(self, method, *args):
    if not self._exists():
      raise ValueError('Cannot call method on undisplayed element.')
    return _proxy(self._guid, {'method': 'call', 'value': args, 'name': method})

  def add_event_listener(self, name, callback):
    """Adds an event listener to the element.

    Args:
      name: Name of the event.
      callback: The python function or js string to evaluate when event occurs.
    Raises:
      ValueError: If callback is not valid.
    """
    msg = {'name': name}
    if isinstance(callback, six.string_types):
      callbacks = self._js_listeners.get(name, {})
      if callback in callbacks:
        raise ValueError('Callback is already added.')
      callbacks[callback] = callback
      self._js_listeners[name] = callbacks
      msg['method'] = 'addJsEventListener'
      msg['value'] = callback
    elif callable(callback):
      callbacks = self._py_listeners.get(name, {})
      if callback in callbacks:
        raise ValueError('Callback is already added.')
      callback_name = str(uuid.uuid4())
      output.register_callback(callback_name, callback)
      callbacks[callback] = callback_name
      self._py_listeners[name] = callbacks
      msg['method'] = 'addPythonEventListener'
      msg['value'] = callback_name
    else:
      raise ValueError('callback must be a js string or callable python')
    if self._exists():
      _proxy(self._guid, msg)

  def remove_event_listener(self, name, callback):
    """Removes an event listener from the element.

    Args:
      name: String of the event.
      callback: The callback passed into add_event_listener previously.
    Raises:
      ValueError: If the callback was not added previously.
    """
    if isinstance(callback, six.string_types):
      listener_map = self._js_listeners
    else:
      listener_map = self._py_listeners
    if name not in listener_map:
      raise ValueError('listener does not exist')
    callbacks = listener_map[name]
    if callback not in callbacks:
      raise ValueError('listener does not exist')
    callback_name = callbacks[callback]
    del callbacks[callback]
    if not callbacks:
      del listener_map[name]
    if self._exists():
      _proxy(self._guid, {
          'method': 'removeEventListener',
          'name': name,
          'value': callback_name
      })

  def append_child(self, child):
    """Append child to Element."""
    # Child could be anything that can be converted to html.
    if isinstance(child, Element):
      child.remove()
      child._parent = self  # pylint: disable=protected-access
    self._children.append(child)

  def remove_child(self, child):
    """Remove child from Element."""
    if isinstance(child, Element):
      if child._parent != self:  # pylint: disable=protected-access
        raise ValueError('Child parent must match.')
      child._parent = None  # pylint: disable=protected-access
    self._children = [c for c in self._children if c is not child]

  def remove(self):
    parent = self._parent
    if not parent:
      return
    parent.remove_child(self)

  def _repr_html_(self):
    """Converts element to HTML string."""
    self._could_exist = True
    deps = ''
    if self._src:
      if 'script' in self._src:
        deps = '<script src="{}"></script>'.format(self._src['script'])
      elif 'module' in self._src:
        deps = '<script type="module">import "{}";</script>'.format(
            self._src['module'])
      elif 'html' in self._src:
        deps = '<link rel="import" href="{}" />'.format(self._src['html'])
    return _element_template.safe_substitute({
        'tag':
            self._tag,
        'guid':
            self._guid,
        'deps':
            deps,
        'utils':
            _utils_url(),
        'children':
            '\n'.join([_to_html_str(c) for c in self._children]),
        'config':
            json.dumps({
                'tag': self._tag,
                'guid': self._guid,
                'attributes': self._attributes,
                'properties': self._properties,
                'js_listeners': {
                    k: list(v.values()) for k, v in self._js_listeners.items()
                },
                'py_listeners': {
                    k: list(v.values()) for k, v in self._py_listeners.items()
                },
            }),
    })
