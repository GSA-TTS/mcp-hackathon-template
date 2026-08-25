# IBM Cloud Deployment (Prebuilt Image) + watsonx Orchestrate

Deploy your MCP server to **IBM Cloud Code Engine** using a **prebuilt public
container image** (e.g., from [GitHub Container Registry / GHCR](https://ghcr.io)
or Docker Hub), then register it as a tool in **watsonx Orchestrate**.

This is the **lowest-authority** Code Engine path: no IBM Container Registry
access is needed. Code Engine simply pulls the image you supply.

> **Which kit is this?** The **prebuilt-image** kit. Use it when you already have
> a public image to deploy. If you want Code Engine to build from your Git repo
> and push to ICR, use the sibling
> [`../code-engine-git-build/`](../code-engine-git-build/README.md) kit instead.
> For no cloud infrastructure at all, use
> [`../local-mcp-toolkit/`](../local-mcp-toolkit/README.md).

> **Hackathon workflow this fits:** build locally → publish image to GHCR →
> deploy to Code Engine → register in watsonx Orchestrate → build an agent that
> uses your tools.

## Getting a public image

You need a public image reference (e.g. `ghcr.io/<user>/<repo>:tag`) before
running the deploy script.

**Option A — Publish your GitHub repo to GHCR (recommended)**

GitHub Actions can build and push your image to GHCR automatically on every
push. See the official guide:
[Working with the Container registry (GitHub Docs)](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)

Once published, make the package **public** in your GitHub account's Packages
settings so Code Engine can pull it without credentials.

**Option B — Use any existing public image**

Set `IMAGE` in your `.env` to any publicly pullable reference:
`docker.io/<user>/<repo>:tag`, `ghcr.io/…`, etc.

## What gets deployed

- **Transport:** MCP over streamable-HTTP at `/mcp`; health check at `/health`
- **Port:** `8080` (set by the template `Dockerfile`)

---

## Part 1 — Prerequisites

### 1.1 Install the IBM Cloud CLI + Code Engine plugin

```bash
# macOS/Linux
curl -fsSL https://clis.cloud.ibm.com/install/osx | sh   # macOS
# or: curl -fsSL https://clis.cloud.ibm.com/install/linux | sh

ibmcloud plugin install code-engine
ibmcloud --version
```

> Alternatively use the browser-based [IBM Cloud Shell](https://cloud.ibm.com/shell),
> which has `ibmcloud` and the `ce` plugin preinstalled.

### 1.2 Log in

```bash
ibmcloud login --sso          # federated / SSO accounts
# or: ibmcloud login --apikey <API_KEY>

ibmcloud resource groups      # note your group (often "Default", sometimes eid-<hash>)
ibmcloud regions              # pick one near you
```

> **Code Engine needs a paid (or trial-upgraded) account** — the free "Lite"
> account cannot create Code Engine projects.

### 1.3 Configure the deploy env file

```bash
cp deploy/ibm/prebuilt-image/.env.example deploy/ibm/prebuilt-image/.env
# edit it:
#   - IBMCLOUD_REGION / IBMCLOUD_RESOURCE_GROUP: match the commands above
#   - CE_APP_NAME: your server's name
#   - IMAGE: full public image reference, e.g. ghcr.io/<you>/<repo>:0.1.0
set -a; source deploy/ibm/prebuilt-image/.env; set +a
```

`.env` holds **no secrets** — only coordinates. It is git-ignored.

---

## Part 2 — Deploy to Code Engine

```bash
set -a; source deploy/ibm/prebuilt-image/.env; set +a
bash deploy/ibm/prebuilt-image/deploy-code-engine.sh
```

The script is idempotent and:

1. Verifies you're logged in; targets your region + resource group.
2. Creates (or selects) the Code Engine project `CE_PROJECT`.
3. Deploys `IMAGE` directly — Code Engine pulls the image and starts the app.
4. Prints the public app URL.

It sets `--min-scale 1` so one instance stays warm — avoiding a cold-start
timeout when an agent makes its first tool call.

### Smoke-test the live endpoint

```bash
bash deploy/ibm/prebuilt-image/smoke-test.sh https://<app>.<region>.codeengine.appdomain.cloud
```

Expected: `/health` → 200 healthy; `/mcp` reachable (a raw curl may return
"Missing session ID" — that's expected; a real client does the MCP handshake).

---

## Part 3 — Register in watsonx Orchestrate (SaaS)

watsonx Orchestrate imports a **remote MCP server** as a **toolkit**.

### 3.1 Install the ADK

```bash
pip install --upgrade ibm-watsonx-orchestrate   # Python 3.11–3.14
orchestrate --version
```

### 3.2 Point the ADK at your instance

Copy the **service instance URL** and an **API key** from the Orchestrate SaaS UI
(Settings → API details), then:

```bash
orchestrate env add --name ibm-saas --url "<YOUR_ORCHESTRATE_INSTANCE_URL>"
orchestrate env activate ibm-saas --api-key "<YOUR_ORCHESTRATE_API_KEY>"
orchestrate env list
```

### 3.3 Add your server as a toolkit

```bash
orchestrate toolkits add \
  --kind mcp \
  --name my_server \
  --description "<what your server does + tool names>" \
  --url "https://<app>.<region>.codeengine.appdomain.cloud/mcp" \
  --transport streamable_http \
  --tools "*"

orchestrate toolkits list
```

> If your ADK version reports a transport mismatch, retry with the base URL (no
> `/mcp`) or `--transport sse`. `sse` and `streamable_http` are the two remote
> transports.

### 3.4 Create an agent that uses the toolkit

In the Orchestrate UI, create/edit an agent, add your toolkit's tools, and give
it a clear instruction. Chat-test one question before relying on it.

---

## Teardown

```bash
set -a; source deploy/ibm/prebuilt-image/.env; set +a
ibmcloud ce app delete --name "${CE_APP_NAME}" -f
# ibmcloud ce project delete --name "${CE_PROJECT}" -f   # removes all apps in it
orchestrate toolkits remove --name my_server
```

---

## Files in this directory

| File | Purpose |
|---|---|
| `.env.example` | Deployment coordinates template (copy to `.env`, no secrets) |
| `deploy-code-engine.sh` | Idempotent deploy — pulls and deploys a prebuilt public image |
| `smoke-test.sh` | Live `/health` + `/mcp` verification |
| `README.md` | This runbook |

## Known gaps / notes

- **Public image only:** the script has no image-pull secret. The image must be
  publicly accessible (GHCR package visibility set to Public, or a public Docker
  Hub repo).
- **No auth on the endpoint:** the MCP endpoint is public with no auth (matches
  the pilot posture). For anything beyond a hackathon, front it with auth.
