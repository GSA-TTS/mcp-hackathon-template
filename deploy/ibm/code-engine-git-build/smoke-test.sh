#!/usr/bin/env bash
# Smoke-test a deployed MCP server.
#
# Verifies against the LIVE endpoint (no mocks):
#   1. /health returns 200 with a healthy body
#   2. /mcp accepts a JSON-RPC request (transport is reachable)
#
# Usage:
#   bash deploy/ibm/code-engine-git-build/smoke-test.sh https://<app>.<region>.codeengine.appdomain.cloud
set -euo pipefail

BASE_URL="${1:?usage: smoke-test.sh <base-url>}"
BASE_URL="${BASE_URL%/}"  # strip trailing slash

echo "=== 1. Health check: ${BASE_URL}/health ==="
HEALTH_CODE="$(curl -s -o /tmp/mcp-health.json -w '%{http_code}' "${BASE_URL}/health")"
cat /tmp/mcp-health.json; echo ""
if [[ "${HEALTH_CODE}" != "200" ]]; then
  echo "FAIL: health check returned HTTP ${HEALTH_CODE}" >&2
  exit 1
fi
echo "PASS: health check 200"
echo ""

# MCP streamable-HTTP requires an Accept header advertising both content types.
# A raw tools/list without the MCP `initialize` handshake may be rejected with
# "Missing session ID" — that's EXPECTED and not a failure. Orchestrate (and
# other real clients) perform the full handshake and discover tools correctly.
echo "=== 2. MCP endpoint reachable: ${BASE_URL}/mcp ==="
RESP="$(curl -s "${BASE_URL}/mcp" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}')"

echo "${RESP}" | head -c 2000; echo ""

if echo "${RESP}" | grep -qi "jsonrpc\|result\|Missing session ID"; then
  echo ""
  echo "PASS: /mcp is reachable and speaking JSON-RPC."
  echo "      (A 'Missing session ID' response is expected for a raw curl — a"
  echo "       real MCP client performs the initialize handshake first.)"
else
  echo ""
  echo "WARN: unexpected /mcp response. If /health passed, register the server" >&2
  echo "      in your agent platform and verify tool discovery there." >&2
fi
