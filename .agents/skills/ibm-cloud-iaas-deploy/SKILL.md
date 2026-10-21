---
name: cr-code-engine-deploy
description: >
  Use when a GSA hackathon participant wants to push their containerized application to IBM Container
  Registry and deploy it on IBM Code Engine — walks through retrieving their personalised helper
  script, installing ibmcloud CLI and the Container Registry plugin, creating an API key and a
  registry secret, pushing the image, and spinning up a Code Engine application. Activate on phrases
  like "push to container registry", "deploy to code engine", "get my helper script", "ibmcloud cr",
  "push my image", or "container registry setup".
---

# GSA Hackathon — Container Registry & Code Engine Deploy

Walk the participant through every step: retrieving their personalised helper script, installing
tooling, creating credentials, pushing their image, and deploying on Code Engine.

---

## Step 1 — Identify the student

Ask the participant for their initials using `ask_followup_question`.

Ask the participant for their student number or cloud account name using `ask_followup_question`.
Accept either form:
- `"Student 7"` / `"7"` / `"student 7"`
- `"itz-saas-813"`

The Container Registry and Code Engine instances the participants have access to are shared tenants. 
To help distinguish this participant's assets from any others, make sure that container images, 
registry and API keys, deployed applications, and other assets have the participant's initials in the 
name, (e.g., "local-container-app-jmd" or "gsa-jmd-mcp-app" as example image names for Jane Marie Doe).

---

## Step 2 — Retrieve the personalised helper script

Use `execute_command` to POST to the self-service API and save the script locally:

```bash
curl -X POST https://cr-helper-api.2fm39a1i8ok7.ca-tor.codeengine.appdomain.cloud/get-script \
  -H "Content-Type: application/json" \
  -d '{"student": "Student <N>"}' \
  -o ~/push-to-cr.sh && chmod +x ~/push-to-cr.sh
```

After saving, display the contents so the participant can verify `IMAGE_NAME`, `RESOURCE_GROUP`,
and `CR_NAMESPACE` are correct for their account:

```bash
cat ~/push-to-cr.sh
```

---

## Step 3 — Install ibmcloud CLI (if not present)

Check whether the CLI is already installed:

```bash
ibmcloud version
```

If the command is not found, install it:

```bash
curl -fsSL https://clis.cloud.ibm.com/install/linux | sh
```

Verify:

```bash
ibmcloud version
```

---

## Step 4 — Install the Container Registry plugin (if not present)

Check:

```bash
ibmcloud cr version
```

If not found, install:

```bash
ibmcloud plugin install container-registry -r 'IBM Cloud'
```

Verify:

```bash
ibmcloud cr version
```

---

## Step 5 — Log in to IBM Cloud

```bash
ibmcloud login --sso
```

Walk the participant through the SSO flow:
1. Open the one-time passcode URL that appears in the terminal.
2. Copy the passcode and paste it back into the terminal.
3. If prompted to select an account, choose their `itz-saas-<NNN>` account.

Target the correct resource group (already in the helper script, but also confirm manually):

```bash
ibmcloud target -g <RESOURCE_GROUP>
```

---

## Step 6 — Create an IBM Cloud API Key

Code Engine needs a registry secret backed by an API key to pull images.
Create a key with the participant's initials appended so keys don't collide:

```bash
ibmcloud iam api-key-create cr-key-<INITIALS> \
  -d "Container Registry key for hackathon participant <INITIALS>" \
  --output json > ~/cr-apikey-<INITIALS>.json
cat ~/cr-apikey-<INITIALS>.json
```

> Ask the participant for their initials before running this command.
> The `apikey` value is shown **once** — copy it for the next step.

---

## Step 7 — Create a registry secret in Code Engine

First, target or create the Code Engine project for the participant's account:

```bash
# If a project already exists:
ibmcloud ce project select --name <CE_PROJECT_NAME>

# If no project exists yet:
ibmcloud ce project create --name hackathon-student<N>
ibmcloud ce project select --name hackathon-student<N>
```

Create the registry secret pointing at the Dallas (`us.icr.io`) Container Registry:

```bash
ibmcloud ce registry create \
  --name cr-secret-<INITIALS> \
  --server us.icr.io \
  --username iamapikey \
  --password <API_KEY_VALUE>
```

Verify:

```bash
ibmcloud ce registry list
```

---

## Step 8 — Build and test the image locally

If the participant has not yet built their container image:

```bash
cd <project-directory>
podman build -t localhost/<IMAGE_NAME>:latest -f Containerfile .
```

Run it locally to confirm it works before pushing:

```bash
podman run --rm -p 8080:8080 localhost/<IMAGE_NAME>:latest
# In another terminal: curl http://localhost:8080/ping
```

---

## Step 9 — Push the image to Container Registry

Run the personalised helper script retrieved in Step 2:

```bash
~/push-to-cr.sh
```

The script will:
1. Log in to IBM Cloud (SSO).
2. Target the correct resource group.
3. Set the CR region to `us-south`.
4. Re-tag the local image for `us.icr.io/<CR_NAMESPACE>/<IMAGE_NAME>:latest`.
5. Log podman into the registry.
6. Push the image.
7. List images in the namespace to confirm the push succeeded.

If any step fails, read the error back to the participant and help resolve it before continuing.

---

## Step 10 — Deploy on Code Engine

Once the image is in Container Registry, create (or update) the Code Engine application.

> **Important:** Code Engine pulls images from `private.us.icr.io`, not `us.icr.io`, even though
> the image was pushed to `us.icr.io`. Always use `private.us.icr.io` in the `--image` flag.

**First-time deploy:**

```bash
ibmcloud ce application create \
  --name <IMAGE_NAME> \
  --image private.us.icr.io/<CR_NAMESPACE>/<IMAGE_NAME>:latest \
  --registry-secret cr-secret-<INITIALS> \
  --port 8080 \
  --min-scale 1
```

**Subsequent updates (re-deploy after a new push):**

```bash
ibmcloud ce application update \
  --name <IMAGE_NAME> \
  --image private.us.icr.io/<CR_NAMESPACE>/<IMAGE_NAME>:latest
```

**Get the public URL:**

```bash
ibmcloud ce application get --name <IMAGE_NAME> --output url
```

Display the URL to the participant and confirm the application is reachable.

---

## Step 11 — Smoke test

```bash
curl https://<APP_URL>/ping
```

Expected response: `pong` (or whatever the application's health endpoint returns).

---

## Troubleshooting quick-reference

| Symptom | Likely cause | Fix |
|---|---|---|
| `ibmcloud: command not found` | CLI not installed | Repeat Step 3 |
| `ibmcloud cr: 'cr' is not a registered command` | Plugin not installed | Repeat Step 4 |
| `unauthorized` on push | Registry secret wrong or expired | Recreate API key and secret (Steps 6–7) |
| CE deploy fails with `UNAUTHORIZED` | Image reference uses `us.icr.io` not `private.us.icr.io` | Use `private.us.icr.io` in `--image` (Step 10) |
| `ImagePullBackOff` in CE | Registry secret not attached or insufficient permissions | Re-run Step 10 with correct `--registry-secret` |
| CE app URL returns 502 | Container crashed on start | Run `ibmcloud ce application logs --name <IMAGE_NAME>` |
| Wrong account targeted | Multiple IBM Cloud accounts | Run `ibmcloud target` and confirm the correct `itz-saas-<NNN>` |
