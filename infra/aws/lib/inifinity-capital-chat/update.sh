#!/bin/bash
set -eux

cd /opt/librechat

# Get Token from SSM Parameter Store
TOKEN=$(aws ssm get-parameter --name /infinity-capital-chat/github-token --with-decryption --query Parameter.Value --output text)

# Pull latest code
git pull https://$TOKEN@github.com//lynx-canadensis/LibreChat.git

# Restart services
docker-compose pull
docker-compose down
docker-compose up -d
