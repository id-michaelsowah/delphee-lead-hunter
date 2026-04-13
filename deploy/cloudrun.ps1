# Deploy Delphee Lead Hunter to Google Cloud Run
# Usage: .\deploy\cloudrun.ps1
# Reads API keys and password from .env in the project root

$PROJECT_ID = "gen-lang-client-0150088450"
$REGION     = "us-central1"
$SERVICE    = "delphee-lead-hunter"
$IMAGE      = "gcr.io/$PROJECT_ID/$SERVICE"

# ── Load .env from project root ───────────────────────────────────────────────
$envFile = Join-Path (Split-Path $PSScriptRoot -Parent) ".env"
foreach ($line in Get-Content $envFile) {
    if ($line -match "^\s*#" -or $line -match "^\s*$") { continue }
    $key, $value = $line -split "=", 2
    Set-Item "env:$($key.Trim())" $value.Trim()
}

Write-Host "==> Deploying $SERVICE to Cloud Run (project: $PROJECT_ID)" -ForegroundColor Cyan

# ── Build and push image ──────────────────────────────────────────────────────
Write-Host "==> Building and pushing Docker image..." -ForegroundColor Cyan
gcloud builds submit --tag $IMAGE --project $PROJECT_ID

# ── Deploy to Cloud Run ───────────────────────────────────────────────────────
Write-Host "==> Deploying to Cloud Run..." -ForegroundColor Cyan
gcloud run deploy $SERVICE `
  --image $IMAGE `
  --region $REGION `
  --platform managed `
  --allow-unauthenticated `
  --port 8000 `
  --memory 1Gi `
  --cpu 1 `
  --timeout 900 `
  --max-instances 1 `
  --set-env-vars "GEMINI_API_KEY=$env:GEMINI_API_KEY" `
  --set-env-vars "ANTHROPIC_API_KEY=$env:ANTHROPIC_API_KEY" `
  --set-env-vars "DB_BACKEND=firestore" `
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID" `
  --set-env-vars "APP_PASSWORD=$env:APP_PASSWORD" `
  --project $PROJECT_ID

# ── Print app URL ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Deployment complete ===" -ForegroundColor Green
gcloud run services describe $SERVICE --region $REGION --project $PROJECT_ID --format "value(status.url)"
