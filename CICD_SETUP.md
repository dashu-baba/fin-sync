# CI/CD Automatic Deployment Setup

## Option 1: Cloud Build Trigger (Recommended)

### Setup Steps:

1. **Connect GitHub Repository**
```bash
# Go to Cloud Build > Triggers in GCP Console
# Click "Connect Repository"
# Select GitHub and authorize
# Choose your fin-sync repository
```

Or via CLI:
```bash
gcloud builds connections create github fin-sync-github \
    --project=compliance-ai-navigator-474121 \
    --region=us-central1
```

2. **Create Trigger**

**Via Console:**
- Go to: https://console.cloud.google.com/cloud-build/triggers?project=compliance-ai-navigator-474121
- Click "Create Trigger"
- Name: `fin-sync-auto-deploy`
- Event: Push to branch
- Source: Your GitHub repo (owner/fin-sync)
- Branch: `^main$`
- Configuration: Cloud Build configuration file
- Location: `/cloudbuild.yaml`
- Substitution variables:
  - `_SERVICE_NAME`: `fin-sync`
  - `_REGION`: `us-central1`
  - `_ARTIFACT_REPO`: `fin-sync-repo`

**Via CLI:**
```bash
gcloud builds triggers create github \
    --name=fin-sync-auto-deploy \
    --project=compliance-ai-navigator-474121 \
    --region=us-central1 \
    --repository=projects/compliance-ai-navigator-474121/locations/us-central1/connections/fin-sync-github/repositories/YOUR_REPO \
    --branch-pattern="^main$" \
    --build-config=cloudbuild.yaml \
    --substitutions=_SERVICE_NAME=fin-sync,_REGION=us-central1,_ARTIFACT_REPO=fin-sync-repo
```

3. **Test It**
```bash
git add .
git commit -m "test: trigger auto-deploy"
git push origin main
```

Monitor build: https://console.cloud.google.com/cloud-build/builds

---

## Option 2: GitHub Actions

### Setup Steps:

1. **Create Service Account**
```bash
# Create service account for GitHub Actions
gcloud iam service-accounts create github-actions-deploy \
    --display-name="GitHub Actions Deployment" \
    --project=compliance-ai-navigator-474121

# Grant permissions
gcloud projects add-iam-policy-binding compliance-ai-navigator-474121 \
    --member="serviceAccount:github-actions-deploy@compliance-ai-navigator-474121.iam.gserviceaccount.com" \
    --role="roles/run.admin"

gcloud projects add-iam-policy-binding compliance-ai-navigator-474121 \
    --member="serviceAccount:github-actions-deploy@compliance-ai-navigator-474121.iam.gserviceaccount.com" \
    --role="roles/cloudbuild.builds.editor"

gcloud projects add-iam-policy-binding compliance-ai-navigator-474121 \
    --member="serviceAccount:github-actions-deploy@compliance-ai-navigator-474121.iam.gserviceaccount.com" \
    --role="roles/iam.serviceAccountUser"
```

2. **Setup Workload Identity Federation**
```bash
# Create workload identity pool
gcloud iam workload-identity-pools create "github-actions-pool" \
    --project="compliance-ai-navigator-474121" \
    --location="global" \
    --display-name="GitHub Actions Pool"

# Create provider
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
    --project="compliance-ai-navigator-474121" \
    --location="global" \
    --workload-identity-pool="github-actions-pool" \
    --display-name="GitHub Provider" \
    --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
    --issuer-uri="https://token.actions.githubusercontent.com"

# Bind service account
gcloud iam service-accounts add-iam-policy-binding \
    github-actions-deploy@compliance-ai-navigator-474121.iam.gserviceaccount.com \
    --project="compliance-ai-navigator-474121" \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/projects/899361706979/locations/global/workloadIdentityPools/github-actions-pool/attribute.repository/YOUR_GITHUB_USERNAME/fin-sync"

# Get the Workload Identity Provider name
gcloud iam workload-identity-pools providers describe "github-provider" \
    --project="compliance-ai-navigator-474121" \
    --location="global" \
    --workload-identity-pool="github-actions-pool" \
    --format="value(name)"
```

3. **Add GitHub Secrets**

Go to: `https://github.com/YOUR_USERNAME/fin-sync/settings/secrets/actions`

Add these secrets:
- `WIF_PROVIDER`: (output from previous command)
- `WIF_SERVICE_ACCOUNT`: `github-actions-deploy@compliance-ai-navigator-474121.iam.gserviceaccount.com`

4. **The workflow is already created at `.github/workflows/deploy.yml`**

5. **Test It**
```bash
git add .
git commit -m "feat: enable GitHub Actions CI/CD"
git push origin main
```

---

## Option 3: Simple Script (Manual but Fast)

Create a git hook to auto-deploy on push:

```bash
# Create post-commit hook
cat > .git/hooks/post-commit << 'EOF'
#!/bin/bash
echo "🚀 Auto-deploying to Cloud Run..."
COMMIT_SHA=$(git rev-parse --short HEAD)
gcloud builds submit \
    --config=cloudbuild.yaml \
    --project=compliance-ai-navigator-474121 \
    --substitutions=_SERVICE_NAME=fin-sync,_REGION=us-central1,_ARTIFACT_REPO=fin-sync-repo,COMMIT_SHA=$COMMIT_SHA \
    --async
echo "✅ Build started! Check: https://console.cloud.google.com/cloud-build/builds"
EOF

chmod +x .git/hooks/post-commit
```

---

## Comparison

| Method | Setup Time | Auto-Deploy | Cost | Best For |
|--------|-----------|-------------|------|----------|
| **Cloud Build Trigger** | 5 min | ✅ Yes | Free tier | Team collaboration |
| **GitHub Actions** | 15 min | ✅ Yes | Free tier | GitHub-centric workflow |
| **Git Hook** | 1 min | ⚠️ Local only | Free | Solo dev, quick setup |

---

## Recommended: Cloud Build Trigger

**Why?**
- ✅ Native GCP integration
- ✅ Automatic on every push to main
- ✅ Build history & logs in GCP Console
- ✅ No external dependencies
- ✅ Free tier: 120 build-minutes/day

**Setup in 2 steps:**
1. Connect GitHub repo in Cloud Console
2. Create trigger pointing to `cloudbuild.yaml`

Done! Every push to `main` auto-deploys.

---

## Testing Auto-Deploy

```bash
# Make a small change
echo "# Auto-deploy test" >> README.md

# Commit and push
git add .
git commit -m "test: auto-deploy"
git push origin main

# Watch the build (if using Cloud Build Trigger)
gcloud builds list --limit=1 --project=compliance-ai-navigator-474121

# Or view in console
# https://console.cloud.google.com/cloud-build/builds
```

---

## Monitoring Deployments

### View Build Logs:
```bash
gcloud builds log $(gcloud builds list --limit=1 --format="value(id)") --stream
```

### View Cloud Run Logs:
```bash
gcloud run services logs read fin-sync --region=us-central1 --limit=50
```

### Set Up Notifications:
- Go to Cloud Build > Settings > Notifications
- Add Slack/Email webhook for build status

---

## Rollback

If auto-deploy breaks something:

```bash
# List revisions
gcloud run revisions list --service=fin-sync --region=us-central1

# Rollback to previous
gcloud run services update-traffic fin-sync \
    --region=us-central1 \
    --to-revisions=fin-sync-00004-w4b=100
```

---

## Best Practices

1. **Use branches:**
   - `main` → auto-deploy to production
   - `dev` → auto-deploy to staging (optional)
   - Feature branches → manual deploy for testing

2. **Add tests to cloudbuild.yaml:**
```yaml
steps:
  # Run tests first
  - name: 'python:3.11'
    entrypoint: python
    args: ['-m', 'pytest', 'tests/']
  
  # Then build & deploy (existing steps)
```

3. **Use tagged releases:**
```bash
git tag v1.0.0
git push origin v1.0.0
# Create separate trigger for tags
```

4. **Enable notifications:**
   - Build failures
   - Deployment success
   - Cloud Run errors

