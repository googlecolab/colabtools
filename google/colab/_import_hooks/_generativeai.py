# Copyright 2023 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Import hook for google.generativeai in Colab.

This will enable the IP geolocation restrictions for the Gemini API to be based
on the location of the user instead of the runtime VM.
"""

import imp  # pylint: disable=deprecated-module
import logging
import os
import sys


class _GenerativeAIImportHook:
  """Enables the Gemini API client library to be customized upon import."""

  def find_module(self, fullname, path=None):
    if fullname != 'google.generativeai':
      return None
    self.module_info = imp.find_module(
        fullname.split('.')[-1], list(path) if path else None
    )
    return self

  def load_module(self, fullname):
    """Loads google.generativeai normally and runs pre-initialization code.

    It runs a background server that intercepts API requests and then proxies
    the requests via the browser.

    Args:
      fullname: fullname of the module

    Returns:
      A modified google.generativeai module.
    """
    previously_loaded = fullname in sys.modules
    generativeai_module = imp.load_module(fullname, *self.module_info)

    if not previously_loaded:
      try:
        import functools  # pylint:disable=g-import-not-at-top
        import json  # pylint:disable=g-import-not-at-top
        import google.api_core.exceptions  # pylint:disable=g-import-not-at-top
        from google.colab import output  # pylint:disable=g-import-not-at-top
        from google.colab.html import _background_server  # pylint:disable=g-import-not-at-top
        import portpicker  # pylint:disable=g-import-not-at-top
        import tornado.web  # pylint:disable=g-import-not-at-top

        def fetch(request):
          path = request.path
          method = request.method
          headers = json.dumps(dict(request.headers))
          body = repr(request.body.decode('utf-8')) if request.body else 'null'
          return output.eval_js("""
            (async () => {{
              // The User-Agent header causes CORS errors in Firefox.
              const headers = {headers};
              delete headers["User-Agent"];
              const response = await fetch(new URL('{path}', 'https://generativelanguage.googleapis.com'), {{
                          method: '{method}',
                          body: {body},
                          headers,
                        }});
              const json = await response.json();
              return json;
            }})()
        """.format(path=path, method=method, headers=headers, body=body))

        class _Redirector(tornado.web.RequestHandler):
          """Redirects API requests to the browser."""

          async def get(self):
            await self._handle_request()

          async def head(self):
            await self._handle_request()

          async def post(self):
            await self._handle_request()

          async def delete(self):
            await self._handle_request()

          async def patch(self):
            await self._handle_request()

          async def put(self):
            await self._handle_request()

          async def options(self):
            await self._handle_request()

          async def _handle_request(self):
            try:
              result = fetch(self.request)
              if isinstance(result, dict) and 'error' in result:
                self.set_status(int(result['error']['code']))
                self.write(result['error']['message'])
                return
              self.write(json.dumps(result))
            except Exception as e:  # pylint:disable=broad-except
              self.set_status(500)
              self.write(str(e))

        class _Proxy(_background_server._BackgroundServer):  # pylint: disable=protected-access
          """Background server that intercepts API requests and then proxies the requests via the browser."""

          def __init__(self):
            app = tornado.web.Application([
                (r'.*', _Redirector),
            ])
            super().__init__(app)

          def create(self, port):
            if self._server_thread is None:
              self.start(port=port)

        port = portpicker.pick_unused_port()

        @functools.cache
        def start():
          p = _Proxy()
          p.create(port=port)
          return p

        start()

        api_endpoint = f'http://localhost:{port}'
        orig_configure = generativeai_module.configure
        generativeai_module.configure = functools.partial(
            orig_configure,
            transport='rest',
            client_options={'api_endpoint': api_endpoint},
        )

        # Change error messages to use the generative language API endpoint
        # instead of the proxy endpoint.
        orig_from_http_response = google.api_core.exceptions.from_http_response

        @functools.wraps(orig_from_http_response)
        def new_from_http_response(*args, **kwargs):
          error = orig_from_http_response(*args, **kwargs)
          error.message = error.message.replace(
              api_endpoint, 'https://generativelanguage.googleapis.com'
          )
          return error

        google.api_core.exceptions.from_http_response = new_from_http_response
      except:  # pylint: disable=bare-except
        logging.exception('Error customizing google.generativeai.')
        os.environ['COLAB_GENERATIVEAI_IMPORT_HOOK_EXCEPTION'] = '1'

    return generativeai_module


def _register_hook():
  sys.meta_path = [_GenerativeAIImportHook()] + sys.meta_path
