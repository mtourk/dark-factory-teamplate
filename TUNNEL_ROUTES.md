# Configure Cloudflare Tunnel Routes

## One-Time Setup: Create the Tunnel Route

Run this command to tell Cloudflare how to route traffic through the tunnel:

### Git Bash:

```bash
TUNNEL_ID="9bdef772-9e7c-495b-a295-6f542c35a1e9"
ACCOUNT_ID="a8e55d73ca21465429eca525015fae88"
TOKEN="cfat_ZJSdt4K6N4AzSv8Xa6K1rI2I3192GITOb9m06r1J123e5a70"
HOSTNAME="factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com"

curl -X PUT "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel/$TUNNEL_ID/routes" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "comment": "Route to local Ollama",
    "routes": [
      {
        "hostname": "'$HOSTNAME'",
        "service": "http://localhost:11434"
      }
    ]
  }'
```

### PowerShell:

```powershell
$tunnelId = "9bdef772-9e7c-495b-a295-6f542c35a1e9"
$accountId = "a8e55d73ca21465429eca525015fae88"
$token = "cfat_ZJSdt4K6N4AzSv8Xa6K1rI2I3192GITOb9m06r1J123e5a70"
$hostname = "factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com"

$body = @{
    comment = "Route to local Ollama"
    routes = @(
        @{
            hostname = $hostname
            service = "http://localhost:11434"
        }
    )
} | ConvertTo-Json

$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}

Invoke-WebRequest -Uri "https://api.cloudflare.com/client/v4/accounts/$accountId/cfd_tunnel/$tunnelId/routes" `
    -Method PUT `
    -Headers $headers `
    -Body $body `
    -UseBasicParsing
```

After running this, you should see a response with `"success": true`.

---

## Then Try Again:

1. **Make sure the tunnel is still running** (from TUNNEL_SETUP.md Step 3)
2. **Run the route configuration command above** (copy the whole thing for Git Bash or PowerShell)
3. **Wait 5 seconds for Cloudflare to propagate**
4. **Test the tunnel** with:

```bash
curl.exe -k https://factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com/api/tags
```

Expected output: the JSON list of your Ollama models (NOT 403 Forbidden).

---

Try this and let me know if the 403 error goes away!
