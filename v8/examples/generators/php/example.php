<?php

#[Attribute(Attribute::TARGET_FUNCTION)]
class UriCommand
{
    public function __construct(
        public string $uri,
        public array $argv,
        public string $label = '',
    ) {}
}

function schemaType(ReflectionParameter $parameter): string
{
    $type = $parameter->getType()?->getName() ?? 'string';
    return match ($type) {
        'int' => 'integer',
        'float' => 'number',
        'bool' => 'boolean',
        default => 'string',
    };
}

function bindingFromFunction(string $function): array
{
    $ref = new ReflectionFunction($function);
    $attr = $ref->getAttributes(UriCommand::class)[0]->newInstance();
    $required = [];
    $properties = [];

    foreach ($ref->getParameters() as $parameter) {
        $schema = ['type' => schemaType($parameter)];
        if ($parameter->isDefaultValueAvailable()) {
            $schema['default'] = $parameter->getDefaultValue();
        } else {
            $required[] = $parameter->getName();
        }
        $properties[$parameter->getName()] = $schema;
    }

    return [
        'uri' => $attr->uri,
        'kind' => 'command',
        'adapter' => 'argv-template',
        'inputSchema' => [
            'type' => 'object',
            'required' => $required,
            'properties' => $properties,
            'additionalProperties' => false,
        ],
        'argv' => $attr->argv,
        'meta' => ['label' => $attr->label],
    ];
}

#[UriCommand(
    uri: 'php://local/slug/create',
    argv: ['php', '-r', "echo strtolower(preg_replace('/[^a-z0-9]+/i', '-', \$argv[1]));", '{text}'],
    label: 'PHP slug',
)]
function slug(string $text, int $limit = 64): void {}

$binding = bindingFromFunction('slug');
echo json_encode(['version' => 'urirun.bindings.v8', 'bindings' => [$binding['uri'] => $binding]], JSON_PRETTY_PRINT) . PHP_EOL;
