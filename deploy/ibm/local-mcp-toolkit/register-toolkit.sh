#!/usr/bin/env bash
# Register this MCP server as a LOCAL MCP toolkit in watsonx Orchestrate.
#
# A local MCP toolkit ships this server's code to Orchestrate, which installs it
# (via requirements.txt at package_root) and runs `python server.py` over stdio
# INSIDE the Orchestrate runtime — no HTTP endpoint, no Code Engine, no container.
#
# Prerequisites:
#   - Python 3.11-3.14
#   - ADK installed:  pip install --upgrade ibm-watsonx-orchestrate
#   - Config:         cp .env.example .env && edit
#
# Usage:
#   set -a; source deploy/ibm/local-mcp-toolkit/.env; set +a
#   #   export WXO_API_KEY="<your key>"     # else you'll be prompted (hidden)
#   bash deploy/ibm/local-mcp-toolkit/register-toolkit.sh
set -euo pipefail

# --- Validate config ----------------------------------------------------------
: "${WXO_ENV_NAME:?set WXO_ENV_NAME (source deploy/ibm/local-mcp-toolkit/.env)}"
: "${WXO_INSTANCE_URL:?set WXO_INSTANCE_URL}"
: "${TOOLKIT_NAME:?set TOOLKIT_NAME}"

# This script lives in the kit dir; toolkit.yaml sits next to it.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# repo root is three levels up: deploy/ibm/local-mcp-toolkit -> repo root
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
STAGE_DIR="${SCRIPT_DIR}/_stage"
TOOLKIT_YAML="${SCRIPT_DIR}/_toolkit.generated.yaml"

# The package to ship. If you renamed `example_server`, set PACKAGE_NAME to match
# (or export it before running).
PACKAGE_NAME="${PACKAGE_NAME:-example_server}"

echo "=== Target ==="
echo "  env name:      ${WXO_ENV_NAME}"
echo "  instance URL:  ${WXO_INSTANCE_URL}"
echo "  toolkit name:  ${TOOLKIT_NAME}"
echo "  package:       ${PACKAGE_NAME}"
echo ""

# --- Confirm the ADK is installed ---------------------------------------------
if ! command -v orchestrate >/dev/null 2>&1; then
  echo "FATAL: 'orchestrate' not found. Install the ADK:" >&2
  echo "       pip install --upgrade ibm-watsonx-orchestrate" >&2
  exit 1
fi

# --- Obtain the API key (never written to disk) -------------------------------
API_KEY="${WXO_API_KEY:-}"
if [[ -z "${API_KEY}" ]]; then
  echo "=== watsonx Orchestrate API key ==="
  read -r -s -p "  API key (input hidden): " API_KEY
  echo ""
  if [[ -z "${API_KEY}" ]]; then
    echo "FATAL: no API key provided." >&2
    exit 1
  fi
fi

# --- Point the ADK at the instance and activate it ----------------------------
echo "=== Configuring ADK environment '${WXO_ENV_NAME}' ==="
if orchestrate env list 2>/dev/null | grep -q "${WXO_ENV_NAME}"; then
  echo "  env exists — reusing."
else
  orchestrate env add --name "${WXO_ENV_NAME}" --url "${WXO_INSTANCE_URL}" --type ibm_iam
fi
orchestrate env activate "${WXO_ENV_NAME}" --api-key "${API_KEY}"
orchestrate env list

# --- Build a minimal, self-contained staging package_root --------------------
# Uploading the whole repo hits a 413 (virtualenvs are large) and can fail the
# server-side install. We stage ONLY what the server needs, FLATTENED out of the
# src/ layout: `${PACKAGE_NAME}/` sits directly at package_root next to
# server.py, so it's importable with no install step.
echo "=== Staging minimal package_root at ${STAGE_DIR} ==="
rm -rf "${STAGE_DIR}"
mkdir -p "${STAGE_DIR}"
cp -R "${REPO_ROOT}/src/${PACKAGE_NAME}" "${STAGE_DIR}/${PACKAGE_NAME}"
cp "${SCRIPT_DIR}/server.py" "${STAGE_DIR}/server.py"
cp "${SCRIPT_DIR}/requirements.txt" "${STAGE_DIR}/requirements.txt"
# Drop caches that may have been copied from src/.
find "${STAGE_DIR}" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
STAGE_SIZE="$(du -sh "${STAGE_DIR}" | cut -f1)"
echo "  staged package_root size: ${STAGE_SIZE}"

# --- Generate the toolkit spec pointing at the staging dir --------------------
sed -E "s#^package_root:.*#package_root: ${STAGE_DIR}#" \
  "${SCRIPT_DIR}/toolkit.yaml" > "${TOOLKIT_YAML}"

# --- Import (or re-import) the local MCP toolkit ------------------------------
echo "=== Importing local MCP toolkit '${TOOLKIT_NAME}' ==="
if orchestrate toolkits list 2>/dev/null | grep -q "${TOOLKIT_NAME}"; then
  echo "  toolkit exists — removing before re-import."
  orchestrate toolkits remove --name "${TOOLKIT_NAME}" || true
fi

orchestrate toolkits import -f "${TOOLKIT_YAML}"

# --- Clean up generated artifacts --------------------------------------------
rm -rf "${STAGE_DIR}" "${TOOLKIT_YAML}"

echo ""
echo "=== Registered ==="
orchestrate toolkits list
echo ""
echo "Next: build/edit an agent in the Orchestrate UI, add the '${TOOLKIT_NAME}'"
echo "tools, and chat-test a question (see README Part 3)."
