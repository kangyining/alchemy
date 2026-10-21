#!/bin/bash
set -euo pipefail

cd /opt/alchemy

# Get Token from SSM Parameter Store
TOKEN=$(aws ssm get-parameter --name /infinity-capital-chat/github-token --with-decryption --query Parameter.Value --output text)

# Pull latest code
git pull --ff-only "https://$TOKEN@github.com/kangyining/alchemy.git" main
unset TOKEN

# Restart services
cd apps/librechat
docker-compose pull
docker-compose down
docker-compose up -d
