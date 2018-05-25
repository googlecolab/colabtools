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
  const bc = new BroadcastChannel(id);
  const respId = 'id' + Math.random();
  msg.reply = respId;

  bc.postMessage(msg);

  const handleMessage = (resolve) => {
    bc.onmessage = (r) => {
      const reply = r.data;
      if (reply.method === 'reply' && reply.id === respId) {
        resolve(reply);
      }
    };
  };

  const response = new Promise(handleMessage).then((reply) => {
    if (reply.error) {
      throw new Error(reply.error);
    }

    return reply.value;
  });

  const values = [response];

  if (defaultResponse !== undefined) {
    values.push(new Promise((resolve) => {
      setTimeout(() => {
        resolve(defaultResponse);
      }, 20);
    }));
  }

  try {
    return await Promise.race(values);
  } finally {
    bc.close();
  }
}
