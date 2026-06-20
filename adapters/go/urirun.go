// Package urirun is the Go SDK for building urirun.bindings.v2 documents.
//
// A connector in any language only has to emit the bindings.v2 contract; this
// package builds it the same way the Python and JS SDKs do, so a Go program can
// be a urirun connector or embed the SDK as a library.
package urirun

import "encoding/json"

// BindingsVersion is the contract version urirun validates against.
const BindingsVersion = "urirun.bindings.v2"

// Schema describes a command's JSON Schema input (object type, no extra props).
type Schema struct {
	Required   []string
	Properties map[string]any
}

type binding struct {
	URI         string         `json:"uri"`
	Kind        string         `json:"kind"`
	Adapter     string         `json:"adapter"`
	InputSchema map[string]any `json:"inputSchema"`
	Argv        []string       `json:"argv"`
	Meta        map[string]any `json:"meta,omitempty"`
	Policy      map[string]any `json:"policy,omitempty"`
}

// Connector accumulates URI command bindings for one scheme.
type Connector struct {
	id       string
	scheme   string
	target   string
	bindings map[string]binding
}

// NewConnector creates a connector that exposes routes under scheme://host/...
func NewConnector(id, scheme string) *Connector {
	return &Connector{id: id, scheme: scheme, target: "host", bindings: map[string]binding{}}
}

// Target overrides the default "host" segment.
func (c *Connector) Target(target string) *Connector {
	c.target = target
	return c
}

// Command declares a route as an argv template filled from the validated payload.
func (c *Connector) Command(route string, schema Schema, argv []string) *Connector {
	uri := c.scheme + "://" + c.target + "/" + route
	props := schema.Properties
	if props == nil {
		props = map[string]any{}
	}
	input := map[string]any{"type": "object", "additionalProperties": false, "properties": props}
	if len(schema.Required) > 0 {
		input["required"] = schema.Required
	}
	c.bindings[uri] = binding{
		URI:         uri,
		Kind:        "command",
		Adapter:     "argv-template",
		InputSchema: input,
		Argv:        argv,
		Meta:        map[string]any{"connector": c.id},
		Policy:      map[string]any{"allowExecute": true},
	}
	return c
}

// Bindings returns the registry-ready bindings.v2 document.
func (c *Connector) Bindings() map[string]any {
	return map[string]any{"version": BindingsVersion, "bindings": c.bindings}
}

// BindingsJSON returns the pretty-printed bindings.v2 document.
func (c *Connector) BindingsJSON() string {
	b, _ := json.MarshalIndent(c.Bindings(), "", "  ")
	return string(b)
}
