# Spartan Coach - Deployment Commands

## Prerequisites

1. Install gcloud CLI: https://cloud.google.com/sdk/docs/install
2. Have your `GOOGLE_API_KEY` (Gemini API key) ready

---

## Quick Deploy (Copy & Paste)

```bash
# 1. Login to Google Cloud
gcloud auth login

# 2. Set your project
gcloud config set project YOUR_PROJECT_ID

# 3. Enable required APIs
gcloud services enable cloudbuild.googleapis.com run.googleapis.com containerregistry.googleapis.com secretmanager.googleapis.com

# 4. Create the GOOGLE_API_KEY secret
echo -n "YOUR_GEMINI_API_KEY" | gcloud secrets create GOOGLE_API_KEY --data-file=-

# 5. Grant Cloud Run access to the secret
gcloud secrets add-iam-policy-binding GOOGLE_API_KEY \
    --member="serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

# 6. Build and deploy
gcloud builds submit --config=cloudbuild.yaml
```

---

## Post-Deploy: Link Secret to Cloud Run

```bash
# Update the service to use the secret
gcloud run services update spartan-coach \
    --region us-central1 \
    --set-secrets "GOOGLE_API_KEY=GOOGLE_API_KEY:latest"
```

---

## Get Your Service URL

```bash
gcloud run services describe spartan-coach --region us-central1 --format 'value(status.url)'
```

---

## Find Your Project Number

```bash
gcloud projects describe YOUR_PROJECT_ID --format="value(projectNumber)"
```

---

## Full Example (Replace placeholders)

```bash
# Set variables
PROJECT_ID="spartan-coach-123"
GOOGLE_API_KEY="AIza..."

# Login and set project
gcloud auth login
gcloud config set project $PROJECT_ID

# Enable APIs
gcloud services enable cloudbuild.googleapis.com run.googleapis.com containerregistry.googleapis.com secretmanager.googleapis.com

# Get project number
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")

# Create secret
echo -n "$GOOGLE_API_KEY" | gcloud secrets create GOOGLE_API_KEY --data-file=- 2>/dev/null || \
echo -n "$GOOGLE_API_KEY" | gcloud secrets versions add GOOGLE_API_KEY --data-file=-

# Grant access
gcloud secrets add-iam-policy-binding GOOGLE_API_KEY \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

# Deploy
gcloud builds submit --config=cloudbuild.yaml

# Link secret to service
gcloud run services update spartan-coach \
    --region us-central1 \
    --set-secrets "GOOGLE_API_KEY=GOOGLE_API_KEY:latest"

# Get URL
gcloud run services describe spartan-coach --region us-central1 --format 'value(status.url)'
```

---

## Redeploy After Code Changes

```bash
gcloud builds submit --config=cloudbuild.yaml
```

---

## View Logs

```bash
gcloud run logs read spartan-coach --region us-central1 --limit 50
```

---

## Delete Deployment

```bash
gcloud run services delete spartan-coach --region us-central1
```
