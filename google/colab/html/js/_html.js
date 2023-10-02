/**
 * @fileoverview Html helper utilities.
 */

(function() {

function safeCopy(obj) {
  const result = {};
  for (const prop in obj) {
    const value = obj[prop];
    if (typeof value !== 'function') {
      try {
        const v = JSON.parse(JSON.stringify(value));
        result[prop] = v;
      } catch (err) {
      }
    }
  }
  return result;
}

const callbacks = new Map();

function addPythonEventListener(element, type, callbackName) {
  const callback = (evt) => {
    google.colab.kernel.invokeFunction(callbackName, [safeCopy(evt)], {});
  };
  callbacks.set(callbackName, callback);
  element.addEventListener(type, callback);
}

function addJsEventListener(element, type, callbackSrc) {
  const fn = new Function('event', callbackSrc);
  const callback = (evt) => {
    fn(evt);
  };
  callbacks.set(callbackSrc, callback);
  element.addEventListener(type, callback);
}

function dotAccess(target, accessor) {
  let obj = target;
  let name = undefined;
  for (const n of accessor.split('.')) {
    if (name !== undefined) {
      obj = obj[name];
    }
    name = n;
  }
  return [obj, name];
}

async function initialize(config) {
  el = document.getElementById(config.guid);
  if (!el) {
    throw new Error(`No element found with id: ${guid}`);
  }
  if (config.tag.includes('-')) {
    await customElements.whenDefined(config.tag);
  }
  if (config.attributes) {
    const att = config.attributes;
    Object.keys(att).forEach((k) => {
      el.setAttribute(k, att[k]);
    });
  }
  if (config.properties) {
    const props = config.properties;
    Object.keys(props).forEach((k) => {
      el[k] = props[k];
    });
  }
  if (config.js_listeners) {
    const jsl = config.js_listeners;
    Object.keys(jsl).forEach((k) => {
      jsl[k].forEach((cb) => {
        addJsEventListener(el, k, cb);
      });
    });
  }
  if (config.py_listeners) {
    const pyl = config.py_listeners;
    Object.keys(pyl).forEach((k) => {
      pyl[k].forEach((cb) => {
        addPythonEventListener(el, k, cb);
      });
    });
  }
}


function processMessage(element, msg) {
  let obj;
  let name;
  if (['call', 'setProperty', 'getProperty'].includes(msg.method)) {
    [obj, name] = dotAccess(element, msg.name);
  }
  switch (msg.method) {
    case 'setProperty':
      obj[name] = msg.value;
      return true;
    case 'getProperty':
      return obj[name];
    case 'setAttribute':
      element.setAttribute(msg.name, msg.value);
      return true;
    case 'getAttribute':
      return element.getAttribute(msg.name);
    case 'call':
      return obj[name](...msg.value);
    case 'addPythonEventListener':
      addPythonEventListener(element, msg.name, msg.value);
      return true;
    case 'addJsEventListener':
      addJsEventListener(element, msg.name, msg.value);
      return true;
    case 'removeEventListener':
      if (callbacks.has(msg.value)) {
        const cb = callbacks.get(msg.value);
        element.removeEventListener(msg.name, cb);
        callbacks.delete(msg.value);
        return true;
      } else {
        throw new Error('Listener is not defined');
      }
    case 'exists':
      return true;
    default:
      throw new Error('Invalid method');
  }
}

function createElement(config) {
  window.google.colab.output.pauseOutputUntil(initialize(config));
  const guid = config.guid;
  const tag = config.tag;
  const el = document.getElementById(guid);
  if (!el) {
    throw new Error(`No element found with id: ${guid}`);
  }
  window.google.colab.html.elements[guid] = {
    call: async (msg) => {
      if (tag.includes('-')) {
        await customElements.whenDefined(tag);
      }
      return processMessage(el, msg);
    }
  };
}

window.google = window.google || {};
window.google.colab = window.google.colab || {};
window.google.colab.html = window.google.colab.html || {
  elements: {},
  _createElement: createElement,
};
})();
