#!/usr/bin/env bash
# A normal bash library with reusable functions. urirun exposes individual
# functions as URIs by sourcing this file and calling one function.

greet() {
  echo "hello, ${1:-world} (from bash function greet)"
}

disk_free() {
  df -h "${1:-/}" | tail -n 1
}
