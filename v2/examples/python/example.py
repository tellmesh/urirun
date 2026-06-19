from urihandler_v2 import dispatch

runtime_cache = {}
registry = {
    'device': {
        'led': {
            'set': lambda target, args, payload, descriptor: {
                'ok': True,
                'target': target,
                'state': args[0] if args else None,
                'payload': payload,
                'descriptor': descriptor,
            }
        }
    },
    'log': {
        'info': {
            'user-created': lambda target, args, payload, descriptor: {
                'ok': True,
                'sink': target,
                'event': 'user-created',
                'args': args,
                'payload': payload,
                'descriptor': descriptor,
            }
        }
    }
}

print(dispatch('device://device-01/led/set/on', registry, {'source': 'frontend'}, runtime_cache))
print(dispatch('log://app/info/user-created', registry, {'userId': 42}, runtime_cache))
