#!/bin/bash
# Deploy report-agents to Google Cloud Run
# Usage: ./deploy.sh
# Reads configuration from .env file

set -euo pipefail

# Load environment variables from .env
if [[ -f .env ]]; then
    echo "Loading .env..."
    set -a
    source .env
    set +a
else
    echo "ERROR: .env file not found"
    exit 1
fi

# Print configuration
echo "=== Configuration ==="
echo "GOOGLE_CLOUD_PROJECT: $GOOGLE_CLOUD_PROJECT"
echo "GOOGLE_CLOUD_LOCATION (Cloud Run): $GOOGLE_CLOUD_LOCATION"
echo "VERTEX_AI_LOCATION (Gemini): ${VERTEX_AI_LOCATION:-global}"
echo "SERVICE_NAME: ${SERVICE_NAME:-report-agents}"
echo "====================="

# Build env vars string
ENV_VARS="GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT"
ENV_VARS+=",GOOGLE_CLOUD_LOCATION=${VERTEX_AI_LOCATION:-global}"
ENV_VARS+=",GOOGLE_GENAI_USE_VERTEXAI=$GOOGLE_GENAI_USE_VERTEXAI"
ENV_VARS+=",DOCAI_LOCATION=$DOCAI_LOCATION"
ENV_VARS+=",DOCAI_PROCESSOR_ID=$DOCAI_PROCESSOR_ID"

echo "Deploying to Cloud Run with custom Dockerfile..."
echo ""

gcloud run deploy "${SERVICE_NAME:-report-agents}" \
    --source . \
    --region "$GOOGLE_CLOUD_LOCATION" \
    --project "$GOOGLE_CLOUD_PROJECT" \
    --set-env-vars="$ENV_VARS" \
    --memory=4Gi \
    --cpu=2 \
    --timeout=300 \
    --allow-unauthenticated
