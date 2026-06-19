import hashlib
import re
from urllib.parse import parse_qsl, unquote, quote

URI_RE = re.compile(r'^(?P<scheme>[a-z][a-z0-9+.-]*)://(?P<target>[^/?#]+)(?P<path>/[^?#]*)?(?:\?(?P<query>[^#]*))?(?:#(?P<fragment>.*))?$', re.I)

def parse_uri(uri: str):
    m = URI_RE.match(str(uri))
    if not m:
        raise ValueError(f'Invalid URI: {uri}')
    segments = [unquote(s) for s in (m.group('path') or '/').split('/') if s]
    return {
        'package': m.group('scheme'),
        'target': unquote(m.group('target')),
        'segments': segments,
        'query': dict(parse_qsl(m.group('query') or '')),
        'fragment': m.group('fragment') or None,
        'raw': uri,
    }

def normalize_uri(d: dict):
    return f"{d['package']}://{d['target']}/{'/'.join(quote(s, safe='') for s in d['segments'])}"

def translate(d: dict):
    resource, operation, *rest = d['segments']
    return {
        'route': [d['package'], resource, operation],
        'args': [d['target'], *rest],
        'package': d['package'],
        'target': d['target'],
        'resource': resource,
        'operation': operation,
        'descriptor': {**d, 'normalized': normalize_uri(d)},
    }

def validate(t: dict, registry: dict):
    return callable(registry.get(t['package'], {}).get(t['resource'], {}).get(t['operation']))

def hash_uri(normalized: str):
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

def resolve(t: dict, registry: dict, runtime_cache: dict | None = None):
    runtime_cache = runtime_cache if runtime_cache is not None else {}
    key = hash_uri(t['descriptor']['normalized'])
    if key in runtime_cache:
        return runtime_cache[key]
    fn = registry.get(t['package'], {}).get(t['resource'], {}).get(t['operation'])
    if not callable(fn):
        raise KeyError(f"Unresolved route: {'.'.join(t['route'])}")
    runtime_cache[key] = fn
    return fn

def dispatch(uri: str, registry: dict, payload=None, runtime_cache: dict | None = None):
    descriptor = parse_uri(uri)
    translation = translate(descriptor)
    if not validate(translation, registry):
        raise ValueError('Route validation failed')
    fn = resolve(translation, registry, runtime_cache)
    return fn(translation['target'], translation['args'][1:], payload, translation['descriptor'])
