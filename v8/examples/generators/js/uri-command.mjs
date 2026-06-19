export function string(options = {}) {
  return { type: 'string', ...options };
}

export function integer(options = {}) {
  return { type: 'integer', ...options };
}

export function boolean(options = {}) {
  return { type: 'boolean', ...options };
}

export function uriCommand(uri, fields, commandFactory, options = {}) {
  const placeholders = Object.fromEntries(Object.keys(fields).map((name) => [name, `{${name}}`]));
  const required = Object.entries(fields)
    .filter(([, schema]) => schema.required)
    .map(([name]) => name);
  const properties = Object.fromEntries(
    Object.entries(fields).map(([name, schema]) => {
      const { required: _required, ...property } = schema;
      return [name, property];
    }),
  );
  return {
    uri,
    kind: options.kind || 'command',
    adapter: options.adapter || 'argv-template',
    inputSchema: {
      type: 'object',
      required,
      properties,
      additionalProperties: false,
    },
    argv: commandFactory(placeholders),
    meta: options.meta || {},
  };
}

export function bindingDocument(bindings) {
  return {
    version: 'urirun.bindings.v8',
    bindings: Object.fromEntries(bindings.map((binding) => [binding.uri, binding])),
  };
}
