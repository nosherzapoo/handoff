# Public Report Request Form — Setup Guide

Two steps to go live. Takes about 5 minutes.

---

## Step 1 — Create a GitHub Personal Access Token (PAT)

The form calls the GitHub API directly using a PAT to trigger the report workflow.
You'll create a tightly scoped token so it can only trigger Actions on this one repo —
nothing else.

1. Go to **GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens**
2. Click **Generate new token**
3. Fill in:
   - **Token name**: `ny-gaming-public-form`
   - **Expiration**: 1 year
   - **Resource owner**: `nosherzapoo`
   - **Repository access**: Only select `OSBdata`
   - **Repository permissions**: `Actions` → **Read and Write** (everything else leave as No access)
4. Click **Generate token**
5. Copy the token (starts with `github_pat_...`) — you only see it once

---

## Step 2 — Add the PAT to `index.html` and enable GitHub Pages

### 2a. Paste the token into the form

Open `index.html` and replace the placeholder on this line:

```js
const GITHUB_TOKEN = 'REPLACE_WITH_YOUR_GITHUB_PAT';
```

with your token, e.g.:

```js
const GITHUB_TOKEN = 'github_pat_11ABCDEF...';
```

Commit and push.

### 2b. Enable GitHub Pages

1. Go to your repo on GitHub → **Settings → Pages**
2. Under **Source**, select **Deploy from a branch**
3. Choose **main** branch, **/ (root)** folder
4. Click **Save**

Your public form will be live at:
```
https://nosherzapoo.github.io/OSBdata/
```
(takes about 1 minute to build the first time)

---

## How it works

```
User visits https://nosherzapoo.github.io/OSBdata/
  → enters email → clicks Submit
  → browser calls GitHub API directly (POST /actions/workflows/dispatches)
  → GitHub Actions runner starts (ny-gaming-manual.yml)
  → pipeline: download → extract → exhibit → email
  → user receives Excel report (~2 min)
```

## Security note

The PAT is visible in the page source. This is intentional and acceptable because:
- The token can **only** trigger GitHub Actions on this one repo
- It cannot read code, push commits, delete branches, or access your SMTP secrets
- Worst case if someone finds it: they trigger a few extra pipeline runs (harmless)
- To invalidate it at any time: delete the token on GitHub and generate a new one

## Auto-scheduler is unaffected

The scheduled workflow (`ny-gaming-monitor.yml`) runs independently on its own cron.
When the public form triggers `ny-gaming-manual.yml`, the report goes only to the
requester's email. When triggered manually from the GitHub UI without an email input,
it falls back to the default `NOTIFICATION_EMAIL1` / `NOTIFICATION_EMAIL2` secrets.
