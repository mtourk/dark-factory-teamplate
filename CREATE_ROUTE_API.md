# Create Tunnel Ingress Config (Correct API Endpoint)

## The Bug

I was using the wrong API endpoint (`/cfd_tunnel/{id}/routes`), which doesn't actually exist for
this purpose — that's why it silently did nothing (empty response, no error).

Since your tunnel was created with `config_src: cloudflare` (a **remotely-managed** tunnel),
the correct way to set routing is the **tunnel configuration** endpoint, which sets the
`ingress` rules directly.

---

## Step 1: Set the Tunnel Configuration (Correct Endpoint)

**Git Bash:**
```bash
TUNNEL_ID="9bdef772-9e7c-495b-a295-6f542c35a1e9"
ACCOUNT_ID="a8e55d73ca21465429eca525015fae88"
TOKEN="cfat_ZJSdt4K6N4AzSv8Xa6K1rI2I3192GITOb9m06r1J123e5a70"
HOSTNAME="factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com"

echo "Setting tunnel configuration..."
curl -s -X PUT "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel/$TUNNEL_ID/configurations" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "ingress": [
        {
          "hostname": "'$HOSTNAME'",
          "service": "http://localhost:11434"
        },
        {
          "service": "http_status:404"
        }
      ]
    }
  }'

echo ""
echo "=== Done - look for \"success\":true above ==="
```

**PowerShell:**
```powershell
$tunnelId = "9bdef772-9e7c-495b-a295-6f542c35a1e9"
$accountId = "a8e55d73ca21465429eca525015fae88"
$token = "cfat_ZJSdt4K6N4AzSv8Xa6K1rI2I3192GITOb9m06r1J123e5a70"
$hostname = "factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com"

$body = @{
    config = @{
        ingress = @(
            @{
                hostname = $hostname
                service = "http://localhost:11434"
            },
            @{
                service = "http_status:404"
            }
        )
    }
} | ConvertTo-Json -Depth 10

$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}

Write-Host "Setting tunnel configuration..."
$result = Invoke-WebRequest -Uri "https://api.cloudflare.com/client/v4/accounts/$accountId/cfd_tunnel/$tunnelId/configurations" `
    -Method PUT `
    -Headers $headers `
    -Body $body `
    -UseBasicParsing

Write-Host $result.Content
```

---

## Step 2: Verify Configuration Was Set

**Git Bash:**
```bash
TUNNEL_ID="9bdef772-9e7c-495b-a295-6f542c35a1e9"
ACCOUNT_ID="a8e55d73ca21465429eca525015fae88"
TOKEN="cfat_ZJSdt4K6N4AzSv8Xa6K1rI2I3192GITOb9m06r1J123e5a70"

echo "=== Current Tunnel Configuration ==="
curl -s "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel/$TUNNEL_ID/configurations" \
  -H "Authorization: Bearer $TOKEN"
```

**PowerShell:**
```powershell
$tunnelId = "9bdef772-9e7c-495b-a295-6f542c35a1e9"
$accountId = "a8e55d73ca21465429eca525015fae88"
$token = "cfat_ZJSdt4K6N4AzSv8Xa6K1rI2I3192GITOb9m06r1J123e5a70"

$headers = @{ "Authorization" = "Bearer $token" }

Write-Host "=== Current Tunnel Configuration ==="
$config = Invoke-WebRequest -Uri "https://api.cloudflare.com/client/v4/accounts/$accountId/cfd_tunnel/$tunnelId/configurations" `
    -Headers $headers -UseBasicParsing
Write-Host $config.Content
```

You should now see your hostname and `localhost:11434` reflected in the ingress rules.

---

## Step 3: Test

Wait 10-15 seconds for propagation, then:

```bash
curl -k https://factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com/api/tags
```

**This should finally return your Ollama models instead of 403!**

---

## If Still 403

The hostname `factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com` might
need a matching DNS record pointing to the tunnel too. If Step 3 still fails after confirming
the config was set (Step 2 shows it), run this to add the DNS record:

**Git Bash:**
```bash
TUNNEL_ID="9bdef772-9e7c-495b-a295-6f542c35a1e9"
/c/Tools/cloudflared/cloudflared.exe tunnel route dns $TUNNEL_ID factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com
```

Note: this might fail if `cloudflareaccess.com` isn't a zone in your account (it's Cloudflare's
own shared domain, not yours) — if so, tell me and we'll pivot to a hostname on a domain you
actually control, or skip DNS and test differently.
