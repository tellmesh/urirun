<?php
return [
    'docs' => [
        'getting-started' => [
            'title' => 'Getting started',
            'description' => 'Install from GitHub, scan artifacts, validate, and run the first URI.',
        ],
        'naming' => [
            'title' => 'Naming',
            'description' => 'Where to use urirun and why the repository URL still contains urihandler.',
        ],
        'commands' => [
            'title' => 'Commands',
            'description' => 'CLI commands, versioned entry points, and one-line binding generation.',
        ],
        'registry-and-bindings' => [
            'title' => 'Registry',
            'description' => 'How portable binding documents become dispatchable runtime routes.',
        ],
        'transports' => [
            'title' => 'Transports',
            'description' => 'Local functions, shell, Docker, HTTP, gRPC, browser, MCP, and A2A.',
        ],
        'logo' => [
            'title' => 'Logo',
            'description' => 'Generated SVG assets for icon, wordmark, favicon, and lockups.',
        ],
        'roadmap' => [
            'title' => 'Roadmap',
            'description' => 'Practical next work for making urirun easier to use.',
        ],
    ],
    'workflow' => [
        ['uri' => 'repo://project/artifacts/query/scan', 'title' => 'Scan artifacts', 'text' => 'Read Dockerfile labels, package metadata, Make targets, shell scripts, and explicit bindings.'],
        ['uri' => 'registry://local/routes/command/compile', 'title' => 'Compile a registry', 'text' => 'Turn portable binding files into one lookup tree for every runtime.'],
        ['uri' => 'policy://local/execution/query/check', 'title' => 'Gate execution', 'text' => 'Dry-run first, then require allow rules for real argv, shell, Docker, or network calls.'],
        ['uri' => 'flow://local/task/command/run', 'title' => 'Run the same URI', 'text' => 'Call it from shell, backend, browser, Docker service, MCP tool, or A2A agent card.'],
    ],
    'features' => [
        ['title' => 'Artifact-first adoption', 'text' => 'Existing Dockerfiles, pyproject scripts, package.json scripts, shell files, and Makefile targets become routes without hand-writing every endpoint.'],
        ['title' => 'Schema-first calls', 'text' => 'v8 bindings use JSON Schema. Python decorators can generate schemas from function signatures through Pydantic.'],
        ['title' => 'One address across layers', 'text' => 'Frontend buttons, backend handlers, shell clients, firmware tables, and service flows can share the same URI naming standard.'],
        ['title' => 'Policy before execution', 'text' => 'Command routes dry-run by default. Real execution is explicit and can be limited by URI allow and deny rules.'],
    ],
    'transports' => [
        ['name' => 'in-process', 'detail' => 'v8.run / local-function dispatch'],
        ['name' => 'argv', 'detail' => 'Safe argument templates, no shell'],
        ['name' => 'shell', 'detail' => 'Policy-gated shell templates'],
        ['name' => 'Docker', 'detail' => 'docker-run / docker-exec, image labels'],
        ['name' => 'HTTP', 'detail' => 'v8_service: POST /run, GET /routes'],
        ['name' => 'gRPC', 'detail' => 'v8_grpc: Run, RunStream, ListRoutes'],
        ['name' => 'queue', 'detail' => 'topic -> v8.run consumer (MQTT/NATS/Kafka shape)'],
        ['name' => 'serverless', 'detail' => 'pure handler(event) function'],
        ['name' => 'MCP / A2A', 'detail' => 'tools/list, tools/call, agent card'],
    ],
    'examples' => [
        ['path' => 'v8/examples/transports', 'text' => 'One registry driven over five transports (in-process, queue, serverless, HTTP, gRPC) plus a simple scan & run.'],
        ['path' => 'v8/examples/multi_transport', 'text' => 'Docker stack mixing HTTP and gRPC workers: auto-generated registry, conflict detection, and a cross-environment flow.'],
        ['path' => 'v8/examples/docker_uri_flow', 'text' => 'Docker Compose services communicating through generated URI bindings, with a library-native service dispatcher.'],
        ['path' => 'v8/examples/novnc_lan_flow', 'text' => 'Four noVNC computers in one Docker LAN, shown together in a dashboard and coordinated by a URI flow.'],
        ['path' => 'v8/examples/html_uri_app', 'text' => 'Browser UI that calls a Python backend through URI actions and exposes logs, MCP tools, and an A2A card.'],
        ['path' => 'v8/examples/generators', 'text' => 'JS, Node.js, TypeScript, and PHP declarations that generate the same v8 binding contract.'],
        ['path' => 'examples/reference_adapters', 'text' => 'Minimal adapters for JavaScript, Python, C/firmware, and browser use.'],
    ],
    'roadmap' => [
        'urirun init for a starter registry, policy, and example route',
        'urirun doctor for environment, dependency, port, and route conflict checks',
        'urirun serve for a local route browser, log viewer, dry-run console, and policy-gated execution',
        'standard log:// routes across frontend, backend, shell, firmware, and Docker examples',
        'urirun diff for comparing registries before deployment',
    ],
];
