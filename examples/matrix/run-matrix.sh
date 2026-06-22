#!/usr/bin/env bash
# Matrix orchestrator (URI-first). Runs INSIDE the urirun image as `matrix`.
#
# The point: ONE URI is the address; every transport just carries it to the same
# run(uri, payload). Each row below shows *where the URI travels* in that transport.
set -uo pipefail
cd /work

REG=/work/hash.bindings.v2.json
URI='hash://host/sha256/command/file'
PAYLOAD='{"path":"/work/sample.txt"}'
fails=0
row() { printf '  %-12s %-34s %s\n' "$1" "$2" "$3"; }
ok_of() { python3 -c 'import json,sys;d=json.load(sys.stdin);print("yes" if d.get("ok") else "no")' 2>/dev/null; }
digest_of() { python3 -c 'import json,sys;d=json.load(sys.stdin);print(((d.get("result") or {}).get("stdout") or "").split()[0][:12])' 2>/dev/null; }

echo "================ urirun matrix — the URI IS the address ================"
echo "address: $URI"
echo "(every transport below carries this same URI to run(uri, payload))"
echo
echo "── addressing the URI over each transport ──"
printf '  %-12s %-34s %s\n' "TRANSPORT" "HOW THE URI IS CARRIED" "RESULT"

# CLI — URI is the positional address
out=$(python -m urirun.runtime.v2 run "$URI" "$REG" --payload "$PAYLOAD" --execute --allow 'hash://**' 2>/dev/null)
[ "$(printf '%s' "$out" | ok_of)" = yes ] \
  && row "CLI" "run('$URI')" "PASS sha256=$(printf '%s' "$out" | digest_of)…" \
  || { row "CLI" "run('$URI')" "FAIL"; fails=$((fails+1)); }

# HTTP node — URI travels in the request body to the generic /run endpoint
out=$(curl -fsS -X POST "http://http-node:8765/run" -H 'content-type: application/json' \
      -d "{\"uri\":\"$URI\",\"payload\":{\"path\":\"/work/sample.txt\"}}" 2>/dev/null)
[ "$(printf '%s' "$out" | ok_of)" = yes ] \
  && row "HTTP node" 'POST /run {"uri":"…"}' "PASS sha256=$(printf '%s' "$out" | digest_of)…" \
  || { row "HTTP node" 'POST /run {"uri":"…"}' "FAIL"; fails=$((fails+1)); }

# gRPC — URI is a field of the Run request
out=$(python -m urirun.runtime.v2_grpc call "$URI" "$REG" --target grpc --payload "$PAYLOAD" --execute 2>/dev/null)
[ "$(printf '%s' "$out" | ok_of)" = yes ] \
  && row "gRPC" 'Run{uri:"…"}' "PASS sha256=$(printf '%s' "$out" | digest_of)…" \
  || { row "gRPC" 'Run{uri:"…"}' "FAIL"; fails=$((fails+1)); }

# MCP — a real tools/call: the tool name maps back to the URI, then run(uri)
tool=$(python -m urirun.runtime.v2_mcp tools "$REG" 2>/dev/null | python3 -c 'import json,sys;print(json.load(sys.stdin)["tools"][0]["name"])' 2>/dev/null)
mcp_out=$(printf '%s\n%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/call\",\"params\":{\"name\":\"$tool\",\"arguments\":{\"path\":\"/work/sample.txt\"}}}" \
  | python -m urirun.runtime.v2_mcp serve "$REG" --execute --policy /work/policy.json 2>/dev/null \
  | python3 -c 'import json,sys
for line in sys.stdin:
    m=json.loads(line)
    if m.get("id")==2:
        env=json.loads(m["result"]["content"][0]["text"]); print("yes" if env.get("ok") else "no", (((env.get("result") or {}).get("stdout") or "").split()+[""])[0][:12])')
[ "${mcp_out%% *}" = yes ] \
  && row "MCP" "tools/call '$tool' → $URI" "PASS sha256=${mcp_out##* }…" \
  || { row "MCP" "tools/call → $URI" "FAIL"; fails=$((fails+1)); }

# flow — each step's .uri is forwarded to the node that owns the URI's target
if flow_out=$(python /work/flow.py 2>/dev/null); then
  row "flow (mesh)" "step.uri=$URI (remote node)" "PASS 2 steps"
else
  row "flow (mesh)" "step.uri=$URI (remote node)" "FAIL"; fails=$((fails+1))
fi

echo
echo "── projecting / routing the same URI (discovery surfaces) ──"
# A2A card advertises the URI as a discoverable skill
python -m urirun.runtime.v2_mcp card "$REG" 2>/dev/null | grep -q "$URI" \
  && row "A2A card" "advertises $URI" "PASS" || { row "A2A card" "advertises $URI" "FAIL"; fails=$((fails+1)); }
# gRPC proto projects the URI's route to a typed rpc
python -m urirun.runtime.v2 gen proto "$REG" 2>/dev/null | grep -q 'rpc Run' \
  && row "gRPC proto" "projects route → rpc" "PASS" || { row "gRPC proto" "projects route → rpc" "FAIL"; fails=$((fails+1)); }
# mesh resolves the URI's target ("host") to a concrete node address
target_node=$(python -m urirun.runtime.v2 host nodes --config /work/mesh.json --json 2>/dev/null \
  | python3 -c 'import json,sys;print(json.load(sys.stdin).get("serviceMap",{}).get("host","-"))' 2>/dev/null)
[ -n "$target_node" ] && [ "$target_node" != "-" ] \
  && row "mesh route" "serviceMap[host] → $target_node" "PASS" \
  || { row "mesh route" "serviceMap[host] → ?" "FAIL"; fails=$((fails+1)); }

echo
echo "── runtimes (every SDK emits the SAME URI route + contract) ──"
python /work/verify.py /shared/python.json /shared/go.json /shared/node.json \
       /shared/php.json /shared/ruby.json /shared/bash.json /shared/rust.json \
       /shared/perl.json /shared/java.json /shared/csharp.json || fails=$((fails+1))

echo
if [ "$fails" -eq 0 ]; then
  echo "RESULT: all matrix cells PASS — one URI ($URI), every transport"
else
  echo "RESULT: $fails cell(s) FAILED"
fi
exit "$fails"
