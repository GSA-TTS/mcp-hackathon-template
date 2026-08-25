#!/usr/bin/env bash
# Deploy a prebuilt public container image to IBM Cloud Code Engine.
#
# This script only supports deploying an image that already exists in a
# publicly accessible container registry (e.g., ghcr.io, docker.io).
# It does NOT build from source or push to IBM Container Registry.
#
# To build and push an image to ICR and deploy from there, use the
# sibling kit: deploy/ibm/code-engine-git-build/
#
# The container serves MCP over streamable-HTTP at :$CE_PORT/mcp with a health
# check at :$CE_PORT/health.
#
# Prerequisites:
#   - IBM Cloud CLI:      https://cloud.ibm.com/docs/cli
#   - Code Engine plugin: ibmcloud plugin install code-engine
#   - Logged in:          ibmcloud login --sso
#   - Config:             cp .env.example .env && edit
#
# Usage:
#   set -a; source deploy/ibm/prebuilt-image/.env; set +a
#   bash deploy/ibm/prebuilt-image/deploy-code-engine.sh
#
# Idempotent: creates the app on first run, updates it on subsequent runs.
set -euo pipefail

# --- Validate config -----------------------------------------------------------
: "${IBMCLOUD_REGION:?set IBMCLOUD_REGION (source deploy/ibm/prebuilt-image/.env)}"
: "${IBMCLOUD_RESOURCE_GROUP:?set IBMCLOUD_RESOURCE_GROUP}"
: "${CE_PROJECT:?set CE_PROJECT}"
: "${CE_APP_NAME:?set CE_APP_NAME}"
: "${CE_PORT:?set CE_PORT}"
: "${IMAGE:?set IMAGE}"

echo "=== Target ==="
echo "  region:         ${IBMCLOUD_REGION}"
echo "  resource group: ${IBMCLOUD_RESOURCE_GROUP}"
echo "  project:        ${CE_PROJECT}"
echo "  app:            ${CE_APP_NAME}"
echo "  port:           ${CE_PORT}"
echo "  image:          ${IMAGE}"
echo ""

# --- Confirm we are logged in -------------------------------------------------
if ! ibmcloud target >/dev/null 2>&1; then
  echo "FATAL: not logged in. Run 'ibmcloud login --sso' first." >&2
  exit 1
fi

# --- Select region + resource group ------------------------------------------
echo "=== Targeting region + resource group ==="
ibmcloud target -r "${IBMCLOUD_REGION}" -g "${IBMCLOUD_RESOURCE_GROUP}"

# --- Ensure the Code Engine project exists and is selected --------------------
echo "=== Selecting Code Engine project '${CE_PROJECT}' ==="
if ibmcloud ce project select --name "${CE_PROJECT}" >/dev/null 2>&1; then
  echo "  project exists — selected."
else
  echo "  project not found — creating '${CE_PROJECT}'..."
  ibmcloud ce project create --name "${CE_PROJECT}"
  ibmcloud ce project select --name "${CE_PROJECT}"
fi

# --- Create or update the application ----------------------------------------
# --port          : container listen port (health checks + traffic routed here)
# --min-scale 1   : keep one instance warm so an eval agent never hits a cold
#                   start mid-experiment (Code Engine scales to zero by default)
# --cpu / --memory: modest sizing; MCP servers are usually I/O-bound
COMMON_ARGS=(
  --name    "${CE_APP_NAME}"
  --image   "${IMAGE}"
  --port    "${CE_PORT}"
  --min-scale 1
  --cpu 0.5
  --memory 1G
)

if ibmcloud ce app get --name "${CE_APP_NAME}" >/dev/null 2>&1; then
  echo "=== Updating existing app '${CE_APP_NAME}' ==="
  ibmcloud ce app update "${COMMON_ARGS[@]}"
else
  echo "=== Creating app '${CE_APP_NAME}' ==="
  ibmcloud ce app create "${COMMON_ARGS[@]}"
fi

# --- Report the public URL ----------------------------------------------------
APP_URL="$(ibmcloud ce app get --name "${CE_APP_NAME}" --output url)"
echo ""
echo "=== Deployed ==="
echo "  App URL:      ${APP_URL}"
echo "  MCP endpoint: ${APP_URL}/mcp"
echo "  Health:       ${APP_URL}/health"
echo ""
echo "Verify with:"
echo "  bash deploy/ibm/prebuilt-image/smoke-test.sh ${APP_URL}"
