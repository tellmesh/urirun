<?php
// urirun — PHP SDK for building urirun.bindings.v2 documents.
//
// A connector in any language only has to emit the bindings.v2 contract; this
// class builds it the same way the Python, JS and Go SDKs do, so a PHP program
// can be a urirun connector or embed the SDK as a library.

declare(strict_types=1);

namespace Urirun;

const BINDINGS_VERSION = 'urirun.bindings.v2';

final class Connector
{
    private string $id;
    private string $scheme;
    private string $target = 'host';
    /** @var array<string,array<string,mixed>> */
    private array $bindings = [];

    public function __construct(string $id, string $scheme)
    {
        $this->id = $id;
        $this->scheme = $scheme;
    }

    public function target(string $target): self
    {
        $this->target = $target;
        return $this;
    }

    /**
     * Declare a route as an argv template filled from the validated payload.
     *
     * @param array{required?:string[],properties?:array<string,mixed>} $schema
     * @param string[] $argv
     */
    public function command(string $route, array $schema, array $argv): self
    {
        $uri = "{$this->scheme}://{$this->target}/{$route}";
        $input = [
            'type' => 'object',
            'additionalProperties' => false,
            'properties' => (object) ($schema['properties'] ?? []),
        ];
        if (!empty($schema['required'])) {
            $input['required'] = array_values($schema['required']);
        }
        $this->bindings[$uri] = [
            'uri' => $uri,
            'kind' => 'command',
            'adapter' => 'argv-template',
            'inputSchema' => $input,
            'argv' => $argv,
            'meta' => ['connector' => $this->id],
            'policy' => ['allowExecute' => true],
        ];
        return $this;
    }

    /** @return array<string,mixed> */
    public function bindings(): array
    {
        return ['version' => BINDINGS_VERSION, 'bindings' => (object) $this->bindings];
    }

    public function bindingsJson(): string
    {
        return json_encode($this->bindings(), JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n";
    }
}
