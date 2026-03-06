#!/usr/bin/env bash
# Build and push the Discord snooker bot image to the Gitea registry.
#
# Usage:
#   ./build-and-push.sh           # tags as :latest
#   ./build-and-push.sh 1.2.3     # tags as :1.2.3 and also :latest

set -euo pipefail

REGISTRY="git.19371928.xyz"
IMAGE_PATH="automation/discord-snooker"
TAG="${1:-latest}"
FULL_IMAGE="${REGISTRY}/${IMAGE_PATH}:${TAG}"

echo "==> Image : ${FULL_IMAGE}"

# Log in to the Gitea registry (no-op if already authenticated)
echo "==> Logging in to ${REGISTRY} ..."
docker login "${REGISTRY}"

# Build
echo "==> Building ${FULL_IMAGE} ..."
docker build -t "${FULL_IMAGE}" .

# Also tag as latest when a specific version was provided
if [ "${TAG}" != "latest" ]; then
    LATEST_IMAGE="${REGISTRY}/${IMAGE_PATH}:latest"
    echo "==> Tagging as ${LATEST_IMAGE} ..."
    docker tag "${FULL_IMAGE}" "${LATEST_IMAGE}"
fi

# Push versioned tag
echo "==> Pushing ${FULL_IMAGE} ..."
docker push "${FULL_IMAGE}"

# Push latest tag if a version was provided
if [ "${TAG}" != "latest" ]; then
    echo "==> Pushing ${LATEST_IMAGE} ..."
    docker push "${LATEST_IMAGE}"
fi

echo "==> Done. Image pushed: ${FULL_IMAGE}"
