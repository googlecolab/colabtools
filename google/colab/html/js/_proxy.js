// Copyright 2018 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License

/**
 * Proxies execution of object across cells.
 * @param {string} id
 * @param {*} msg
 * @param {*} defaultResponse response if id does not exist
 * @returns {Promise}
 */
async function proxy(id, msg, defaultResponse) {
  let elementProxy = null;
  for (let i = 0; i < window.parent.frames.length; ++i) {
    const frame = window.parent.frames[i];
    // The frames will include cross-origin frames which will generate errors
    // when accessing the contents, so guard against that.
    try {
      const html = frame.window.google.colab.html;
      if (html) {
        elementProxy = html.elements[id];
        if (elementProxy) {
          break;
        }
      }
    } catch (e) {
      // Continue to the next frame.
    }
  }
  if (!elementProxy) {
    return defaultResponse;
  }
  return elementProxy.call(msg);
}

//# sourceURL=/google/colab/html/js/_proxy.js
