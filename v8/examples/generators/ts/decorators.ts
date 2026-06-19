type JsonType = 'string' | 'integer' | 'number' | 'boolean';

type Field = {
  type: JsonType;
  required?: boolean;
  default?: string | number | boolean;
};

type CommandBinding = {
  uri: string;
  kind: 'command';
  adapter: 'argv-template';
  inputSchema: {
    type: 'object';
    required: string[];
    properties: Record<string, Omit<Field, 'required'>>;
    additionalProperties: false;
  };
  argv: string[];
};

const registry: Record<string, CommandBinding> = {};

function uriCommand(uri: string, fields: Record<string, Field>) {
  return function (_value: unknown, context: ClassMethodDecoratorContext) {
    context.addInitializer(function () {
      const method = (this as Record<string, Function>)[String(context.name)];
      const placeholders = Object.fromEntries(Object.keys(fields).map((name) => [name, `{${name}}`]));
      const properties = Object.fromEntries(
        Object.entries(fields).map(([name, field]) => {
          const { required: _required, ...schema } = field;
          return [name, schema];
        }),
      );
      registry[uri] = {
        uri,
        kind: 'command',
        adapter: 'argv-template',
        inputSchema: {
          type: 'object',
          required: Object.entries(fields).filter(([, field]) => field.required).map(([name]) => name),
          properties,
          additionalProperties: false,
        },
        argv: method.call(this, placeholders),
      };
    });
  };
}

class MathCommands {
  @uriCommand('ts://local/math/add', {
    a: { type: 'integer', required: true },
    b: { type: 'integer', default: 0 },
  })
  add({ a, b }: { a: string; b: string }) {
    return ['node', '-e', 'console.log(Number(process.argv[1]) + Number(process.argv[2]))', a, b];
  }
}

new MathCommands();
console.log(JSON.stringify({ version: 'urirun.bindings.v8', bindings: registry }, null, 2));
