#!/bin/bash
# Deploy Delphee Lead Hunter to Google Cloud Run
# Usage: ./deploy/cloudrun.sh YOUR_GCP_PROJECT_ID
#
# Prerequisites:
#   - gcloud CLI installed and authenticated (gcloud auth login)
#   - Docker installed locally
#   - GEMINI_API_KEY and ANTHROPIC_API_KEY set in your shell environment

set -e

PROJECT_ID=$1
if [ -z "$PROJECT_ID" ]; then
  echo "Usage: ./deploy/cloudrun.sh YOUR_GCP_PROJECT_ID"
  exit 1
fi

REGION="us-central1"
SERVICE_NAME="delphee-lead-hunter"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "==> Deploying ${SERVICE_NAME} to Cloud Run in project ${PROJECT_ID}"

# Enable required GCP APIs
echo "==> Enabling GCP APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  containerregistry.googleapis.com \
  firestore.googleapis.com \
  --project ${PROJECT_ID}

# Create Firestore database (native mode, if it doesn't exist)
echo "==> Creating Firestore database (if needed)..."
gcloud firestore databases create \
  --location=${REGION} \
  --project ${PROJECT_ID} 2>/dev/null || echo "Firestore database already exists — skipping"

# Build and push image to Google Container Registry
echo "==> Building and pushing Docker image..."
gcloud builds submit --tag ${IMAGE} --project ${PROJECT_ID}

# Deploy to Cloud Run
echo "==> Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE} \
  --region ${REGION} \
  --platform managed \
  --allow-unauthenticated \
  --port 8000 \
  --memory 1Gi \
  --cpu 1 \
  --timeout 900 \
  --max-instances 1 \
  --set-env-vars "GEMINI_API_KEY=${GEMINI_API_KEY}" \
  --set-env-vars "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}" \
  --set-env-vars "DB_BACKEND=firestore" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
  --set-env-vars "APP_PASSWORD=${APP_PASSWORD}" \
  --project ${PROJECT_ID}

echo ""
echo "=== Deployment complete! ==="
echo "Your app URL:"
gcloud run services describe ${SERVICE_NAME} \
  --region ${REGION} \
  --project ${PROJECT_ID} \
  --format 'value(status.url)'
echo ""
echo "To map a custom domain (e.g. leads.delphee.de):"
echo "  gcloud run domain-mappings create --service ${SERVICE_NAME} --domain YOUR_DOMAIN --region ${REGION}"
