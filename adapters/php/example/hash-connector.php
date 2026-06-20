<?php
// Reference urirun connector in PHP: prints a urirun.bindings.v2 document.
//   php example/hash-connector.php > bindings.json
//   urirun validate bindings.json && urirun compile bindings.json --out registry.json
declare(strict_types=1);
require __DIR__ . '/../Urirun.php';

$c = new Urirun\Connector('hash', 'hash');
$c->command(
    'sha256/command/file',
    ['required' => ['path'], 'properties' => ['path' => ['type' => 'string', 'title' => 'Path']]],
    ['sha256sum', '{path}']
);
echo $c->bindingsJson();
