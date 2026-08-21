# IBM Code Engine — Build-from-Git Deployment

Deploy your MCP server to **IBM Cloud Code Engine** by **building directly from a
public Git repo**: Code Engine clones the repo, builds its `Dockerfile`
**server-side**, pushes the resulting image to **your IBM Container Registry
(ICR) namespace**, then deploys it. **No local Docker, no manual push.**

> **Which kit is this?** The **build-from-Git** kit — the intended "point Code
> Engine at your repo and go" experience. It requires **ICR authority**
> (namespace create/write + an API key for the push secret). If your account
> lacks that, use the sibling [`../prebuilt-image/`](../prebuilt-image/README.md)
> kit (deploy a public image, no registry write). For no cloud infra at all, use
> [`../local-mcp-toolkit/`](../local-mcp-toolkit/README.md).

## How it differs from the prebuilt-image kit

| | This kit | `../prebuilt-image/` |
|---|---|---|
| Source | Code Engine builds your **Git repo** | You supply a **prebuilt image** ref |
| Local Docker | **Not needed** | Needed to build/push the image |
| Image registry | Pushes to **your ICR namespace** | Any public registry (e.g. GHCR) |
| Extra IBM authority | **ICR namespace + API key** | None |

---

## Part 1 — Prerequisites

### 1.1 Install the CLI + plugins

```bash
curl -fsSL https://clis.cloud.ibm.com/install/osx | sh    # or .../linux
ibmcloud plugin install code-engine
ibmcloud plugin install container-registry
```

### 1.2 Log in and discover your account's values

```bash
ibmcloud login --sso
ibmcloud resource groups      # NOTE: many accounts have NO "Default" group
ibmcloud regions
ibmcloud cr region            # your CURRENT ICR region + domain
ibmcloud cr namespace-list    # existing ICR namespaces (may be pre-provisioned)
```

> **Account-reality gotchas:**
> - **Resource group:** there may be no `Default`; use the generated `eid-<hash>`.
> - **ICR region is often `global` (`icr.io`)** and is independent of your Code
>   Engine region. A CE app in `us-east` pushing to `icr.io` is valid.
> - **Reuse a pre-provisioned namespace** if one exists — you then need no
>   namespace-create authority.

> **Authority required:** permission to create an ICR namespace (or Writer on an
> existing one) **and** to create an IAM API key. If `namespace-add` or
> `api-key-create` fails, fall back to `../prebuilt-image/`.

### 1.3 Configure the deploy env file

```bash
cp deploy/ibm/code-engine-git-build/.env.example deploy/ibm/code-engine-git-build/.env
# edit using the values discovered above; set GIT_REPO_URL to your PUBLIC fork
set -a; source deploy/ibm/code-engine-git-build/.env; set +a
```

### 1.4 Provide an IBM Cloud API key (for the ICR push secret)

```bash
export IBMCLOUD_API_KEY="$(ibmcloud iam api-key-create ce-icr-push \
    -d 'Code Engine ICR push' --output json | jq -r .apikey)"
```

If unset, the script prompts (hidden). Delete when done:
`ibmcloud iam api-key-delete ce-icr-push`.

---

## Part 2 — Deploy (build from Git)

```bash
set -a; source deploy/ibm/code-engine-git-build/.env; set +a
bash deploy/ibm/code-engine-git-build/deploy-build-from-git.sh
```

The script is idempotent and:

1. Targets your region + resource group.
2. Ensures the ICR namespace exists (create-or-reuse).
3. Creates/updates the Code Engine registry secret from your API key.
4. Creates (or selects) the Code Engine project.
5. Runs `ce app create/update --build-source …`: clone → build → push → deploy.
6. Prints the public app URL and the ICR image reference.

### Smoke-test

```bash
bash deploy/ibm/code-engine-git-build/smoke-test.sh https://<app>.<region>.codeengine.appdomain.cloud
```

Confirm the image landed in ICR:

```bash
ibmcloud cr region-set "${ICR_REGION}"
ibmcloud cr images --restrict "${ICR_NAMESPACE}"
```

---

## Part 3 — Register in watsonx Orchestrate

Registration is **identical regardless of how the server was deployed** — the
Orchestrate side only sees the public `/mcp` URL. Follow **Part 3** of the
sibling runbook [`../prebuilt-image/README.md`](../prebuilt-image/README.md),
using the Code Engine URL this kit printed.

---

## Teardown

```bash
set -a; source deploy/ibm/code-engine-git-build/.env; set +a
ibmcloud ce app delete --name "${CE_APP_NAME}" -f
# ibmcloud ce registry delete --name "${CE_REGISTRY_SECRET}" -f
# ibmcloud ce project delete --name "${CE_PROJECT}" -f
ibmcloud cr region-set "${ICR_REGION}"
# ibmcloud cr image-rm "${ICR_DOMAIN}/${ICR_NAMESPACE}/${CE_APP_NAME}:${IMAGE_TAG}"
# ibmcloud iam api-key-delete ce-icr-push
```

---

## Files in this directory

| File | Purpose |
|---|---|
| `.env.example` | Deployment coordinates template (copy to `.env`, no secrets) |
| `deploy-build-from-git.sh` | Idempotent build-from-Git deploy (namespace → secret → build+deploy) |
| `smoke-test.sh` | Live `/health` + `/mcp` verification |
| `README.md` | This runbook |

## Known gaps / notes

- **Public-repo only:** private repos need a Code Engine Git secret +
  `--build-git-repo-secret` (out of scope here).
- **API key handling:** read from `IBMCLOUD_API_KEY` or prompted (hidden), never
  written to disk. Rotate/delete when done.
- **Region pairing:** the ICR region is independent of the Code Engine region;
  set `ICR_REGION` / `ICR_DOMAIN` from `ibmcloud cr region`.
- **No auth on the endpoint:** public with no auth (pilot posture). Front it with
  auth for anything beyond a hackathon.
