#!/usr/bin/env bash
# Build and push the Discord snooker bot image to the Gitea registry.
# After a successful push the image tag in deploy.yaml is updated.
#
# Usage:
#   ./build-and-push.sh           # tags with UTC timestamp (yyyyMMdd-HHmmss)
#   ./build-and-push.sh 1.2.3     # tags as :1.2.3

set -euo pipefail

REGISTRY="git.19371928.xyz"
IMAGE_PATH="automation/discord-snooker"
TAG="${1:-$(date -u +"%Y%m%d-%H%M%S")}"
FULL_IMAGE="${REGISTRY}/${IMAGE_PATH}:${TAG}"
DEPLOY_FILE="$(cd "$(dirname "$0")" && pwd)/deploy.yaml"

echo "==> Image : ${FULL_IMAGE}"

# Log in to the Gitea registry (no-op if already authenticated)
echo "==> Logging in to ${REGISTRY} ..."
docker login "${REGISTRY}"

# Build
echo "==> Building ${FULL_IMAGE} ..."
docker build -t "${FULL_IMAGE}" .

# Push
echo "==> Pushing ${FULL_IMAGE} ..."
docker push "${FULL_IMAGE}"

# Update the image tag in deploy.yaml
echo "==> Updating image tag in deploy.yaml ..."
sed -i "s|${REGISTRY}/${IMAGE_PATH}:[^ ]*|${FULL_IMAGE}|g" "${DEPLOY_FILE}"
echo "==> deploy.yaml updated to ${FULL_IMAGE}"

echo "==> Done. Image pushed: ${FULL_IMAGE}"
