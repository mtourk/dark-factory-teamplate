#!/bin/bash
# Cloudflare Tunnel Setup for Ollama (Bash/Git Bash version)

# Step 1: Get the tunnel token

echo "Getting tunnel token from Cloudflare..."

TOKEN_RESPONSE=$(curl -s -X GET \
  "https://api.cloudflare.com/client/v4/accounts/a8e55d73ca21465429eca525015fae88/cfd_tunnel/9bdef772-9e7c-495b-a295-6f542c35a1e9/token" \
  -H "Authorization: Bearer cfat_ZJSdt4K6N4AzSv8Xa6K1rI2I3192GITOb9m06r1J123e5a70")

echo "Full response:"
echo "$TOKEN_RESPONSE"
echo ""

# Extract the token (looks for the "result" field)
TUNNEL_TOKEN=$(echo "$TOKEN_RESPONSE" | grep -o '"result":"[^"]*' | cut -d'"' -f4)

if [ -z "$TUNNEL_TOKEN" ]; then
  echo "ERROR: Could not extract tunnel token. Check the response above."
  exit 1
fi

echo "✓ Tunnel token extracted successfully"
echo ""
echo "TUNNEL_TOKEN=$TUNNEL_TOKEN"
echo ""

# Step 2: Install cloudflared (if not already installed)

echo "Checking if cloudflared is installed..."
if ! command -v cloudflared &> /dev/null; then
  echo "cloudflared not found. Installing..."
  # For Windows, you may need to download manually from:
  # https://github.com/cloudflare/cloudflared/releases
  echo "Please download cloudflared from: https://github.com/cloudflare/cloudflared/releases"
  echo "Or on macOS/Linux, run: brew install cloudflare/cloudflare/cloudflared"
  exit 1
fi

echo "✓ cloudflared is installed: $(cloudflared --version)"
echo ""

# Step 3: Run the tunnel

echo "Starting tunnel..."
echo "Command:"
echo "  cloudflared tunnel run --token $TUNNEL_TOKEN"
echo ""
echo "Running now... (press Ctrl+C to stop)"
echo ""

cloudflared tunnel run --token "$TUNNEL_TOKEN"
