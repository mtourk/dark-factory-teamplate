# Cloudflare Tunnel Debugging - Fix the Route

## Step 1: Verify Tunnel Status

### Git Bash:
```bash
TUNNEL_ID="9bdef772-9e7c-495b-a295-6f542c35a1e9"
ACCOUNT_ID="a8e55d73ca21465429eca525015fae88"
TOKEN="cfat_ZJSdt4K6N4AzSv8Xa6K1rI2I3192GITOb9m06r1J123e5a70"

echo "=== Checking tunnel status ==="
curl -s -X GET "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel/$TUNNEL_ID" \
  -H "Authorization: Bearer $TOKEN" | head -c 500

echo ""
echo ""
echo "=== Checking tunnel routes ==="
curl -s -X GET "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel/$TUNNEL_ID/routes" \
  -H "Authorization: Bearer $TOKEN" | head -c 500
```

### PowerShell:
```powershell
$tunnelId = "9bdef772-9e7c-495b-a295-6f542c35a1e9"
$accountId = "a8e55d73ca21465429eca525015fae88"
$token = "cfat_ZJSdt4K6N4AzSv8Xa6K1rI2I3192GITOb9m06r1J123e5a70"

$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}

Write-Host "=== Checking tunnel status ==="
$tunnelStatus = Invoke-WebRequest -Uri "https://api.cloudflare.com/client/v4/accounts/$accountId/cfd_tunnel/$tunnelId" `
    -Headers $headers `
    -UseBasicParsing
Write-Host $tunnelStatus.Content

Write-Host ""
Write-Host "=== Checking tunnel routes ==="
$routes = Invoke-WebRequest -Uri "https://api.cloudflare.com/client/v4/accounts/$accountId/cfd_tunnel/$tunnelId/routes" `
    -Headers $headers `
    -UseBasicParsing
Write-Host $routes.Content
```

**Copy the full output and paste it here. Look for:**
- Is the tunnel "healthy" or "connected"?
- Does it show any existing routes?
- Any error messages?

---

## Step 2: Delete Old Route (if exists)

If the routes endpoint shows something, try to delete it first:

### Git Bash:
```bash
TUNNEL_ID="9bdef772-9e7c-495b-a295-6f542c35a1e9"
ACCOUNT_ID="a8e55d73ca21465429eca525015fae88"
TOKEN="cfat_ZJSdt4K6N4AzSv8Xa6K1rI2I3192GITOb9m06r1J123e5a70"
HOSTNAME="factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com"

echo "Deleting old route..."
curl -s -X DELETE "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel/$TUNNEL_ID/routes/$HOSTNAME" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | cat

echo ""
echo "Done"
```

### PowerShell:
```powershell
$tunnelId = "9bdef772-9e7c-495b-a295-6f542c35a1e9"
$accountId = "a8e55d73ca21465429eca525015fae88"
$token = "cfat_ZJSdt4K6N4AzSv8Xa6K1rI2I3192GITOb9m06r1J123e5a70"
$hostname = "factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com"

$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}

Write-Host "Deleting old route..."
$deleteResult = Invoke-WebRequest -Uri "https://api.cloudflare.com/client/v4/accounts/$accountId/cfd_tunnel/$tunnelId/routes/$hostname" `
    -Method DELETE `
    -Headers $headers `
    -UseBasicParsing
Write-Host $deleteResult.Content

Write-Host "Done"
```

---

## Step 3: Create Route Properly

This is the corrected route creation command (simpler format):

### Git Bash:
```bash
TUNNEL_ID="9bdef772-9e7c-495b-a295-6f542c35a1e9"
ACCOUNT_ID="a8e55d73ca21465429eca525015fae88"
TOKEN="cfat_ZJSdt4K6N4AzSv8Xa6K1rI2I3192GITOb9m06r1J123e5a70"
HOSTNAME="factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com"

echo "Creating route..."
curl -s -X POST "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel/$TUNNEL_ID/routes" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "hostname": "'$HOSTNAME'",
    "service": "http://localhost:11434",
    "comment": "Ollama bridge"
  }' | cat

echo ""
echo "Done - check output above for success"
```

### PowerShell:
```powershell
$tunnelId = "9bdef772-9e7c-495b-a295-6f542c35a1e9"
$accountId = "a8e55d73ca21465429eca525015fae88"
$token = "cfat_ZJSdt4K6N4AzSv8Xa6K1rI2I3192GITOb9m06r1J123e5a70"
$hostname = "factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com"

$body = @{
    hostname = $hostname
    service = "http://localhost:11434"
    comment = "Ollama bridge"
} | ConvertTo-Json

$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}

Write-Host "Creating route..."
$result = Invoke-WebRequest -Uri "https://api.cloudflare.com/client/v4/accounts/$accountId/cfd_tunnel/$tunnelId/routes" `
    -Method POST `
    -Headers $headers `
    -Body $body `
    -UseBasicParsing

Write-Host $result.Content
Write-Host ""
Write-Host "Done - check output above for success"
```

---

## Step 4: Verify Route Was Created

### Git Bash:
```bash
TUNNEL_ID="9bdef772-9e7c-495b-a295-6f542c35a1e9"
ACCOUNT_ID="a8e55d73ca21465429eca525015fae88"
TOKEN="cfat_ZJSdt4K6N4AzSv8Xa6K1rI2I3192GITOb9m06r1J123e5a70"

echo "Current routes:"
curl -s -X GET "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel/$TUNNEL_ID/routes" \
  -H "Authorization: Bearer $TOKEN" | cat

echo ""
echo "Done"
```

### PowerShell:
```powershell
$tunnelId = "9bdef772-9e7c-495b-a295-6f542c35a1e9"
$accountId = "a8e55d73ca21465429eca525015fae88"
$token = "cfat_ZJSdt4K6N4AzSv8Xa6K1rI2I3192GITOb9m06r1J123e5a70"

$headers = @{
    "Authorization" = "Bearer $token"
}

Write-Host "Current routes:"
$routes = Invoke-WebRequest -Uri "https://api.cloudflare.com/client/v4/accounts/$accountId/cfd_tunnel/$tunnelId/routes" `
    -Headers $headers `
    -UseBasicParsing
Write-Host $routes.Content
```

---

## Step 5: Wait and Test

Wait 10 seconds, then test:

```bash
curl.exe -k https://factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com/api/tags
```

Expected: JSON with your Ollama models (not 403 Forbidden)

---

## If Still 403:

Run these diagnostics:

### Check tunnel is connected (Git Bash):
```bash
TUNNEL_ID="9bdef772-9e7c-495b-a295-6f542c35a1e9"
ACCOUNT_ID="a8e55d73ca21465429eca525015fae88"
TOKEN="cfat_ZJSdt4K6N4AzSv8Xa6K1rI2I3192GITOb9m06r1J123e5a70"

echo "Tunnel connections:"
curl -s -X GET "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel/$TUNNEL_ID/connections" \
  -H "Authorization: Bearer $TOKEN" | cat
```

### Check local Ollama is running:
```bash
curl http://localhost:11434/api/tags
```

Should return JSON with models. If this fails, Ollama crashed - restart it.
