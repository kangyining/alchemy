#!/bin/bash
# Deploy report-agents to Google Cloud Run
# Usage: ./deploy.sh
# Reads configuration from .env file
#
# The container runs Hypercorn on main:app (see Dockerfile). With --use-http2,
# Cloud Run sends HTTP/2 cleartext (h2c) to the container; Hypercorn handles that
# on the plain bind. For local TLS + ALPN h2: hypercorn main:app -b 0.0.0.0:8443
# --certfile cert.pem --keyfile key.pem. Uvicorn 0.40+ has no --http2 flag.
#
# 413 + "nginx/..." in the HTML: a reverse proxy in front of this service is
# rejecting large bodies (nginx default client_max_body_size is 1m). Fix on the
# proxy host, not in this repo — see deploy/nginx-reverse-proxy.example.conf

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
echo "ASGI server (container): Hypercorn main:app (HTTP/2: h2c on Cloud Run, ALPN h2 with local TLS)"
echo "====================="

# Build env vars string
ENV_VARS="GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT"
ENV_VARS+=",GOOGLE_CLOUD_LOCATION=${VERTEX_AI_LOCATION:-global}"
ENV_VARS+=",GOOGLE_GENAI_USE_VERTEXAI=$GOOGLE_GENAI_USE_VERTEXAI"
ENV_VARS+=",DOCAI_LOCATION=$DOCAI_LOCATION"
ENV_VARS+=",DOCAI_PROCESSOR_ID=$DOCAI_PROCESSOR_ID"
if [[ -n "${REPORTS_BUCKET:-}" ]]; then
    ENV_VARS+=",REPORTS_BUCKET=$REPORTS_BUCKET"
fi

echo "Deploying to Cloud Run with custom Dockerfile..."
echo ""

gcloud run deploy "${SERVICE_NAME:-report-agents}" \
    --source . \
    --region "$GOOGLE_CLOUD_LOCATION" \
    --project "$GOOGLE_CLOUD_PROJECT" \
    --set-env-vars="$ENV_VARS" \
    --memory=4Gi \
    --cpu=2 \
    --use-http2 \
    --timeout=3600 \
    --allow-unauthenticated
