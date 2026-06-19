import { dispatch } from './urihandler-v2.js';

const runtimeCache = new Map();
const registry = {
  device: {
    led: {
      set(target, args, payload, descriptor) {
        return { ok: true, target, state: args[0], payload, descriptor };
      }
    }
  },
  log: {
    info: {
      'user-created'(target, args, payload, descriptor) {
        return { ok: true, sink: target, event: 'user-created', args, payload, descriptor };
      }
    }
  }
};

console.log(await dispatch('device://device-01/led/set/on', registry, { source: 'frontend' }, runtimeCache));
console.log(await dispatch('log://app/info/user-created', registry, { userId: 42 }, runtimeCache));
