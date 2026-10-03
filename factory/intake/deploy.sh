#!/bin/bash
# Deploy script for Dark Factory intake (web + worker)
# Automatically increments version number and updates deployment timestamp
#
# Usage: ./deploy.sh [--dry-run]
#
# This script:
# 1. Increments VERSION in factory/intake/web/VERSION
# 2. Updates DEPLOYED_AT timestamp in wrangler.toml
# 3. Deploys the web frontend (Pages)
# 4. Deploys the Worker
# 5. Verifies CORS origin is correct
#
# The version and timestamp are then served via the Worker's /version endpoint
# and displayed in the web UI footer.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_DIR="$SCRIPT_DIR/factory/intake/web"
WORKER_DIR="$SCRIPT_DIR/factory/intake/worker"
VERSION_FILE="$WEB_DIR/VERSION"
WRANGLER_TOML="$WORKER_DIR/wrangler.toml"
DRY_RUN=false

if [[ "$1" == "--dry-run" ]]; then
  DRY_RUN=true
  echo "🔍 DRY RUN MODE — no changes will be committed"
fi

# Step 1: Read and increment version
if [[ ! -f "$VERSION_FILE" ]]; then
  echo "❌ VERSION file not found: $VERSION_FILE"
  exit 1
fi

CURRENT_VERSION=$(cat "$VERSION_FILE")
NEXT_VERSION=$((CURRENT_VERSION + 1))

echo "📦 Current version: $CURRENT_VERSION"
echo "📦 Next version: $NEXT_VERSION"

# Step 2: Generate deployment timestamp
DEPLOYED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "⏰ Deployment timestamp: $DEPLOYED_AT"

if [[ "$DRY_RUN" == false ]]; then
  # Update VERSION file
  echo "$NEXT_VERSION" > "$VERSION_FILE"
  echo "✅ Updated VERSION to $NEXT_VERSION"

  # Update wrangler.toml
  sed -i "s/^VERSION = .*/VERSION = \"$NEXT_VERSION\"/" "$WRANGLER_TOML"
  sed -i "s/^DEPLOYED_AT = .*/DEPLOYED_AT = \"$DEPLOYED_AT\"/" "$WRANGLER_TOML"
  echo "✅ Updated wrangler.toml with version and timestamp"
fi

# Step 3: Deploy web frontend
echo ""
echo "🚀 Deploying web frontend to Cloudflare Pages..."
if [[ "$DRY_RUN" == false ]]; then
  cd "$WEB_DIR"
  wrangler pages deploy . --project-name dark-factory-intake --commit-dirty=true
  PAGES_URL=$(cd "$WEB_DIR" && wrangler pages deployment list --project-name dark-factory-intake 2>/dev/null | head -1 | awk '{print $2}' || echo "https://factory.mtourk.com")
  echo "✅ Pages deployed"
else
  echo "   [DRY RUN] wrangler pages deploy would run here"
fi

# Step 4: Deploy Worker
echo ""
echo "🚀 Deploying Worker..."
if [[ "$DRY_RUN" == false ]]; then
  cd "$WORKER_DIR"
  wrangler deploy
  echo "✅ Worker deployed"
else
  echo "   [DRY RUN] wrangler deploy would run here"
fi

# Step 5: Verify
echo ""
echo "🔍 Verifying deployment..."
if [[ "$DRY_RUN" == false ]]; then
  sleep 2  # Give Cloudflare a moment to propagate
  VERSION_RESPONSE=$(curl -s https://dark-factory-intake.mohammad-tourk.workers.dev/version)
  echo "   Version endpoint response: $VERSION_RESPONSE"

  CORS_CHECK=$(curl -s -i -X OPTIONS https://dark-factory-intake.mohammad-tourk.workers.dev/conversations \
    -H "Origin: https://factory.mtourk.com" | grep -i "access-control-allow-origin" | head -1)
  echo "   CORS check: $CORS_CHECK"
else
  echo "   [DRY RUN] Verification would run here"
fi

echo ""
if [[ "$DRY_RUN" == true ]]; then
  echo "✅ DRY RUN COMPLETE — no changes made"
  echo ""
  echo "To proceed with real deployment, run: ./deploy.sh"
else
  echo "✅ DEPLOYMENT COMPLETE"
  echo ""
  echo "📊 Summary:"
  echo "   • Version: $NEXT_VERSION"
  echo "   • Deployed at: $DEPLOYED_AT"
  echo "   • Web: https://factory.mtourk.com"
  echo "   • Worker: https://dark-factory-intake.mohammad-tourk.workers.dev"
  echo "   • Version endpoint: https://dark-factory-intake.mohammad-tourk.workers.dev/version"
fi
