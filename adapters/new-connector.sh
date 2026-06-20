#!/usr/bin/env bash
# Scaffold a starter urirun connector in a chosen language.
#
# Usage: adapters/new-connector.sh --lang go|php <id> [scheme] [out-dir]
#   --lang   target language (go or php). Python/JS scaffolds live elsewhere.
#   <id>     kebab-case connector id (e.g. weather-now)
#   [scheme] URI scheme (default: id with dashes removed)
#   [out]    output directory (default: ./urirun-connector-<id>-<lang>)
#
# The generated connector emits the same urirun.bindings.v2 contract as every
# other language, so `urirun validate/compile/list` works on its output.
set -euo pipefail

LANG_CHOICE=""
if [ "${1:-}" = "--lang" ]; then LANG_CHOICE="${2:-}"; shift 2; fi
ID="${1:?usage: new-connector.sh --lang go|php <id> [scheme] [out-dir]}"
SCHEME="${2:-${ID//-/}}"
OUT="${3:-./urirun-connector-${ID}-${LANG_CHOICE}}"
case "$LANG_CHOICE" in go|php) ;; *) echo "error: --lang must be go or php" >&2; exit 2;; esac
[ -e "$OUT" ] && { echo "target already exists: $OUT" >&2; exit 1; }
mkdir -p "$OUT"

if [ "$LANG_CHOICE" = "go" ]; then
  cat > "$OUT/go.mod" <<EOF
module example.com/urirun-connector-${ID}

go 1.21

require github.com/if-uri/urirun/adapters/go v0.0.0
EOF
  cat > "$OUT/main.go" <<EOF
package main

import (
	"fmt"

	urirun "github.com/if-uri/urirun/adapters/go"
)

func main() {
	c := urirun.NewConnector("${ID}", "${SCHEME}")
	c.Command(
		"example/command/run",
		urirun.Schema{
			Required:   []string{"input"},
			Properties: map[string]any{"input": map[string]any{"type": "string"}},
		},
		[]string{"echo", "{input}"},
	)
	fmt.Println(c.BindingsJSON())
}
EOF
elif [ "$LANG_CHOICE" = "php" ]; then
  cat > "$OUT/connector.php" <<EOF
<?php
declare(strict_types=1);
// require the urirun PHP SDK (composer require if-uri/urirun, or path include)
require __DIR__ . '/Urirun.php';

\$c = new Urirun\\Connector('${ID}', '${SCHEME}');
\$c->command(
    'example/command/run',
    ['required' => ['input'], 'properties' => ['input' => ['type' => 'string']]],
    ['echo', '{input}']
);
echo \$c->bindingsJson();
EOF
fi

cat > "$OUT/README.md" <<EOF
# urirun-connector-${ID} (${LANG_CHOICE})

Starter urirun connector. Emit and run its bindings:

\`\`\`bash
$([ "$LANG_CHOICE" = go ] && echo 'go run . > bindings.json' || echo 'php connector.php > bindings.json')
urirun validate bindings.json
urirun compile bindings.json --out registry.json
urirun list registry.json
\`\`\`

Contract: https://docs.ifuri.com/generating-connectors.html
EOF

echo "scaffolded ${LANG_CHOICE} connector '${ID}' (scheme ${SCHEME}://) -> $OUT"
