// Reference urirun connector in Go: prints a urirun.bindings.v2 document.
//
//	go run ./example/hash-connector > bindings.json
//	urirun validate bindings.json && urirun compile bindings.json --out registry.json
package main

import (
	"fmt"

	urirun "github.com/if-uri/urirun/adapters/go"
)

func main() {
	c := urirun.NewConnector("hash", "hash")
	c.Command(
		"sha256/command/file",
		urirun.Schema{
			Required:   []string{"path"},
			Properties: map[string]any{"path": map[string]any{"type": "string", "title": "Path"}},
		},
		[]string{"sha256sum", "{path}"},
	)
	fmt.Println(c.BindingsJSON())
}
