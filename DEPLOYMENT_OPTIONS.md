# Cloud Run Deployment Options

## ✅ GitHub Push Complete!
**Commit**: 8fff00c  
**Status**: Pushed to main  
**CI/CD**: Running in GitHub Actions

---

## Cloud Run Deployment - Choose One

### Option A: Install gcloud CLI (15 min)

**Download**: https://cloud.google.com/sdk/docs/install

**After install**:
```bash
# Authenticate
gcloud auth login

# Deploy
gcloud run deploy inventory-agent \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars="API_KEY=your-key,GOOGLE_API_KEY=$GOOGLE_API_KEY"
```

---

### Option B: GitHub Actions Auto-Deploy (Recommended)

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Cloud Run

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write

    steps:
      - uses: actions/checkout@v3
      
      - id: auth
        uses: google-github-actions/auth@v1
        with:
          workload_identity_provider: ${{ secrets.GCP_WORKLOAD_IDENTITY_PROVIDER }}
          service_account: ${{ secrets.GCP_SERVICE_ACCOUNT }}
      
      - name: Deploy to Cloud Run
        uses: google-github-actions/deploy-cloudrun@v1
        with:
          service: inventory-agent
          region: us-central1
          source: .
          env_vars: |
            API_KEY=${{ secrets.API_KEY }}
            GOOGLE_API_KEY=${{ secrets.GOOGLE_API_KEY }}
```

**Setup**:
1. Add GitHub secrets: `GOOGLE_API_KEY`, `API_KEY`
2. Setup GCP workload identity
3. Push triggers auto-deploy

---

### Option C: Docker + Cloud Run Console

```bash
# Build Docker image
docker build -t gcr.io/YOUR-PROJECT/inventory-agent .

# Push (requires docker login)
docker push gcr.io/YOUR-PROJECT/inventory-agent

# Deploy via console: https://console.cloud.google.com/run
```

---

### Option D: Demo on Localhost (Tonight)

**Skip deployment for now** and:
1. Record demo video using localhost:8000
2. Deploy tomorrow when fresh
3. Re-record with live URL later

**Benefit**: Still get portfolio-worthy demo tonight

---

## Recommendation

**Tonight**: Option D (demo on localhost)  
**Tomorrow**: Option A or B (proper deployment)

You're at 1:45 AM - a great demo on localhost is better than rushing Cloud setup.
